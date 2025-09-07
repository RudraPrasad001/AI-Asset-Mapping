import ee
import datetime
import logging
from typing import Dict, Any

logger = logging.getLogger("aoi-mapper")

def initialize_earth_engine(project_id: str = None):
    """Initialize Earth Engine with optional project ID."""
    try:
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()
        logger.info("Initialized Earth Engine.")
    except Exception as e:
        logger.info("Earth Engine not initialized, attempting Authenticate() -> Initialize()")
        ee.Authenticate()
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()

def mask_s2_clouds(img: ee.Image) -> ee.Image:
    """Mask clouds in Sentinel-2 imagery."""
    qa = img.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
        qa.bitwiseAnd(cirrus_bit_mask).eq(0)
    )
    return img.updateMask(mask).copyProperties(img, img.propertyNames())

def sentinel2_composite(aoi: ee.Geometry, start_days: int = 365) -> ee.Image:
    """Create a Sentinel-2 composite for the given area."""
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
    water_mask: ee.Image, 
    forest_mask: ee.Image, 
    agri_mask: ee.Image, 
    aoi: ee.Geometry
) -> Dict[str, float]:
    """Compute areas for each land cover type."""
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
    """Safely convert a mask to vector format."""
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
