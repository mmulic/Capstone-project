"""
GeoJSON Service (BE-008)
=========================
Converts property + prediction data into GeoJSON FeatureCollection
for the React/Leaflet map frontend. Supports bounding box filtering via PostGIS.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, cast, Float
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from geoalchemy2.functions import ST_MakeEnvelope, ST_Within

from app.models.models import Property, Prediction, DamageClass


DAMAGE_COLORS = {
    DamageClass.NO_DAMAGE: "#27AE60",
    DamageClass.MINOR: "#F39C12",
    DamageClass.MAJOR: "#E67E22",
    DamageClass.DESTROYED: "#E74C3C",
}


class GeoJSONService:
    """Generates GeoJSON FeatureCollections from property/prediction data."""

    async def get_feature_collection(
        self,
        db: AsyncSession,
        sw_lat: Optional[float] = None,
        sw_lng: Optional[float] = None,
        ne_lat: Optional[float] = None,
        ne_lng: Optional[float] = None,
        damage_level: Optional[str] = None,
        confidence_min: Optional[float] = None,
    ) -> dict:
        """
        Build a GeoJSON FeatureCollection with optional bounding box and damage filters.

        Args:
            db: Database session
            sw_lat/sw_lng: Southwest corner of bounding box
            ne_lat/ne_lng: Northeast corner of bounding box
            damage_level: Filter by damage class
            confidence_min: Minimum confidence threshold
        """
        # Build query — join properties with their latest prediction
        latest_pred = (
            select(
                Prediction.property_id,
                Prediction.damage_class,
                Prediction.confidence,
                Prediction.rationale,
                Prediction.created_at,
                func.row_number()
                .over(
                    partition_by=Prediction.property_id,
                    order_by=Prediction.created_at.desc(),
                )
                .label("rn"),
            )
            .subquery()
        )

        query = (
            select(
                Property.id,
                Property.external_id,
                Property.address,
                Property.latitude,
                Property.longitude,
                Property.city,
                Property.state,
                latest_pred.c.damage_class,
                latest_pred.c.confidence,
                latest_pred.c.rationale,
            )
            .outerjoin(
                latest_pred,
                and_(
                    Property.id == latest_pred.c.property_id,
                    latest_pred.c.rn == 1,
                ),
            )
        )

        # Apply bounding box filter using PostGIS
        if all(v is not None for v in [sw_lat, sw_lng, ne_lat, ne_lng]):
            bbox = ST_MakeEnvelope(sw_lng, sw_lat, ne_lng, ne_lat, 4326)
            query = query.where(ST_Within(Property.location, bbox))

        # Apply damage level filter
        if damage_level:
            try:
                damage_enum = DamageClass(damage_level)
                query = query.where(latest_pred.c.damage_class == damage_enum)
            except ValueError:
                pass

        # Apply confidence filter
        if confidence_min is not None:
            query = query.where(latest_pred.c.confidence >= confidence_min)

        result = await db.execute(query)
        rows = result.all()

        features = []
        for row in rows:
            damage = row.damage_class
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [row.longitude, row.latitude],
                },
                "properties": {
                    "id": str(row.id),
                    "external_id": row.external_id,
                    "address": row.address,
                    "city": row.city,
                    "state": row.state,
                    "damage_class": damage.value if damage else None,
                    "confidence": round(row.confidence, 3) if row.confidence else None,
                    "rationale": row.rationale,
                    "color": DAMAGE_COLORS.get(damage, "#808080") if damage else "#808080",
                    "assessed": damage is not None,
                },
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_features": len(features),
                "assessed": sum(1 for f in features if f["properties"]["assessed"]),
                "unassessed": sum(1 for f in features if not f["properties"]["assessed"]),
                "bounding_box": (
                    {"sw": [sw_lat, sw_lng], "ne": [ne_lat, ne_lng]}
                    if all(v is not None for v in [sw_lat, sw_lng, ne_lat, ne_lng])
                    else None
                ),
            },
        }


# Singleton
geojson_service = GeoJSONService()
