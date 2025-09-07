from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import ee
import math
import logging
from utils.earth_engine import (
    sentinel2_composite,
    compute_mask_areas,
    safe_vectorize
)

router = APIRouter(prefix="/api/aoi", tags=["AOI Mapper"])
logger = logging.getLogger("aoi-mapper")

class InputModel(BaseModel):
    name: str
    latitude: float
    longitude: float
    area_sq_m: float

@router.post("/analyze")
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
            "layers": layers
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
