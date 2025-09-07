from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import math
import ee
import datetime
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aoi-mapper")

# Initialize Earth Engine
GEE_PROJECT = "carbon-segment-466615-n9"

try:
    if GEE_PROJECT:
        ee.Initialize(project=GEE_PROJECT)
    else:
        ee.Initialize()
    logger.info("Initialized Earth Engine.")
except Exception as e:
    logger.info("Earth Engine not initialized, attempting Authenticate() -> Initialize()")
    ee.Authenticate()
    if GEE_PROJECT:
        ee.Initialize(project=GEE_PROJECT)
    else:
        ee.Initialize()

app = FastAPI(title="AOI Mapper API")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InputModel(BaseModel):
    name: str
    latitude: float
    longitude: float
    area_sq_m: float


def mask_s2_clouds(img: ee.Image) -> ee.Image:
    qa = img.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
        qa.bitwiseAnd(cirrus_bit_mask).eq(0)
    )
    return img.updateMask(mask).copyProperties(img, img.propertyNames())


def sentinel2_composite(aoi: ee.Geometry, start_days: int = 365) -> ee.Image:
    now_dt = datetime.datetime.utcnow()
    end = ee.Date(now_dt)
    start = end.advance(-int(start_days), "day")

    collection_id = "COPERNICUS/S2_SR_HARMONIZED"
    col = (
        ee.ImageCollection(collection_id)
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        .map(mask_s2_clouds)
    )

    col_size = col.size().getInfo()
    if col_size == 0:
        raise RuntimeError(
            f"No Sentinel-2 images found for AOI/date range (last {start_days} days)."
        )

    img = col.median().clip(aoi)
    return img


def compute_mask_areas(
    water_mask: ee.Image, forest_mask: ee.Image, agri_mask: ee.Image, aoi: ee.Geometry
) -> Dict[str, float]:
    def area_sum(mask_img: ee.Image, scale: int = 10) -> float:
        pixel_area = ee.Image.pixelArea()
        s = pixel_area.updateMask(mask_img).reduceRegion(
            reducer=ee.Reducer.sum(), geometry=aoi, scale=scale, maxPixels=1e13
        )
        v = s.getInfo().get("area", 0.0)
        return float(v or 0.0)

    water_area = area_sum(water_mask)
    forest_area = area_sum(forest_mask)
    agri_area = area_sum(agri_mask)
    total_area = float(aoi.area(1).getInfo() or 0.0)
    infra_area = max(total_area - (water_area + forest_area + agri_area), 0.0)

    return {
        "water_area": water_area,
        "forest_area": forest_area,
        "agri_area": agri_area,
        "infra_area": infra_area,
        "total_area": total_area,
    }


def safe_vectorize(mask_img: ee.Image, aoi: ee.Geometry, label: str) -> Dict[str, Any]:
    pixel_area = ee.Image.pixelArea()
    s = pixel_area.updateMask(mask_img).reduceRegion(
        reducer=ee.Reducer.sum(), geometry=aoi, scale=10, maxPixels=1e13
    )
    area_val = 0.0
    try:
        area_val = float(s.getInfo().get("area", 0.0) or 0.0)
    except Exception:
        area_val = 0.0

    if area_val <= 0.0:
        return {"type": "FeatureCollection", "features": []}

    vec = mask_img.selfMask().reduceToVectors(
        geometry=aoi,
        scale=10,
        geometryType="polygon",
        labelProperty="label",
        maxPixels=1e13,
        bestEffort=True,
    )

    def _set_props(f):
        return f.set({"class": label, "area_sq_m": f.geometry().area(1)})

    vec = vec.map(_set_props)

    try:
        return ee.FeatureCollection(vec).getInfo()
    except Exception as e:
        logger.exception("reduceToVectors/getInfo failed for label=%s: %s", label, e)
        return {"type": "FeatureCollection", "features": []}


@app.post("/analyze")
async def analyze_area(payload: InputModel):
    """Analyze a single area of interest."""
    try:
        if payload.area_sq_m <= 0:
            raise HTTPException(status_code=400, detail="area_sq_m must be > 0")

        radius_m = math.sqrt(payload.area_sq_m / math.pi)
        center = ee.Geometry.Point([payload.longitude, payload.latitude])
        aoi = center.buffer(radius_m)

        try:
            img = sentinel2_composite(aoi, start_days=365)
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndwi = img.normalizedDifference(["B3", "B8"]).rename("NDWI")

        ndwi_t = 0.3
        ndvi_agri_t = 0.35
        ndvi_forest_t = 0.6

        water_mask = ndwi.gt(ndwi_t)
        forest_mask = ndvi.gt(ndvi_forest_t)
        agri_mask = ndvi.gt(ndvi_agri_t).And(forest_mask.Not()).And(
            water_mask.Not()
        )
        combined = water_mask.add(forest_mask).add(agri_mask)
        infra_mask = combined.eq(0)

        areas = compute_mask_areas(water_mask, forest_mask, agri_mask, aoi)
        total_area = areas["total_area"]
        water_area = areas["water_area"]
        forest_area = areas["forest_area"]
        agri_area = areas["agri_area"]
        infra_area = areas["infra_area"]

        if total_area <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Computed AOI total area is zero for {payload.name}.",
            )

        def pct(x):
            return round(100.0 * x / total_area, 4)

        summary = {
            "name": payload.name,
            "input_area_sq_m": payload.area_sq_m,
            "calculated_radius_m": radius_m,
            "total_area_sq_m": total_area,
            "agriculture_area_sq_m": agri_area,
            "agriculture_pct": pct(agri_area),
            "water_area_sq_m": water_area,
            "water_pct": pct(water_area),
            "forest_area_sq_m": forest_area,
            "forest_pct": pct(forest_area),
            "infrastructure_area_sq_m": infra_area,
            "infrastructure_pct": pct(infra_area),
            "latitude": payload.latitude,
            "longitude": payload.longitude,
        }

        # Get GeoJSON for each layer
        water_geo = safe_vectorize(water_mask, aoi, "water")
        agri_geo = safe_vectorize(agri_mask, aoi, "agriculture")
        forest_geo = safe_vectorize(forest_mask, aoi, "forest")
        infra_geo = safe_vectorize(infra_mask, aoi, "infrastructure")

        # Convert to array of layers with properties
        layers = []
        for geo, class_name in [
            (water_geo, "water"),
            (agri_geo, "agriculture"),
            (forest_geo, "forest"),
            (infra_geo, "infrastructure")
        ]:
            if geo and geo.get("features"):
                for feature in geo["features"]:
                    feature["properties"]["class"] = class_name
                    layers.append(feature)

        return {
            "summary": summary,
            "layers": layers  # Array of GeoJSON features with class property
        }

    except HTTPException:
        raise
    except ee.EEException as e:
        logger.exception("Earth Engine exception: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Earth Engine error: {e}"
        )
    except Exception as e:
        logger.exception("Unhandled exception in /analyze: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Server error: {e}"
        )
