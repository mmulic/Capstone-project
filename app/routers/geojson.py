"""
GeoJSON Router (BE-008)
========================
GET /api/geojson — Returns damage data as GeoJSON FeatureCollection for map overlay.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.geojson_service import geojson_service

router = APIRouter(prefix="/api", tags=["GeoJSON"])


@router.get("/geojson")
async def get_geojson(
    sw_lat: Optional[float] = Query(None, description="Southwest corner latitude"),
    sw_lng: Optional[float] = Query(None, description="Southwest corner longitude"),
    ne_lat: Optional[float] = Query(None, description="Northeast corner latitude"),
    ne_lng: Optional[float] = Query(None, description="Northeast corner longitude"),
    damage_level: Optional[str] = Query(None, description="Filter: no_damage, minor_damage, major_damage, destroyed"),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get damage assessment data as GeoJSON FeatureCollection.

    Use bounding box params to filter to a map viewport.
    Each feature includes: coordinates, damage_class, confidence, color code, address.

    Frontend usage:
    ```js
    const response = await fetch('/api/geojson?sw_lat=29.7&sw_lng=-95.5&ne_lat=29.8&ne_lng=-95.3');
    const geojson = await response.json();
    L.geoJSON(geojson).addTo(map);
    ```
    """
    return await geojson_service.get_feature_collection(
        db=db,
        sw_lat=sw_lat,
        sw_lng=sw_lng,
        ne_lat=ne_lat,
        ne_lng=ne_lng,
        damage_level=damage_level,
        confidence_min=confidence_min,
    )
