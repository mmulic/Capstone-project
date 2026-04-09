"""
Stats Router (BE-018)
======================
GET /api/stats — Dashboard summary statistics
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Property, Prediction, DamageClass
from app.schemas.schemas import DashboardStats

router = APIRouter(prefix="/api", tags=["Results"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """
    Return dashboard summary statistics:
    - Total properties in the system
    - Total properties assessed (have at least one prediction)
    - Damage distribution (count per classification level)
    - Average prediction confidence
    - Date range of assessments

    Used by the frontend for summary cards displayed above the map.
    """
    # Total properties
    total_result = await db.execute(select(func.count(Property.id)))
    total_properties = total_result.scalar() or 0

    # Total assessed (distinct properties with predictions)
    assessed_result = await db.execute(
        select(func.count(func.distinct(Prediction.property_id)))
    )
    total_assessed = assessed_result.scalar() or 0

    # Damage distribution
    dist_result = await db.execute(
        select(Prediction.damage_class, func.count(Prediction.id))
        .group_by(Prediction.damage_class)
    )
    damage_distribution = {}
    for row in dist_result.all():
        damage_distribution[row[0].value] = row[1]

    # Ensure all classes present (even if zero)
    for dc in DamageClass:
        if dc.value not in damage_distribution:
            damage_distribution[dc.value] = 0

    # Average confidence
    avg_result = await db.execute(select(func.avg(Prediction.confidence)))
    avg_confidence = avg_result.scalar()

    # Date range
    date_range = None
    if total_assessed > 0:
        min_date_result = await db.execute(
            select(func.min(Prediction.created_at))
        )
        max_date_result = await db.execute(
            select(func.max(Prediction.created_at))
        )
        min_date = min_date_result.scalar()
        max_date = max_date_result.scalar()
        if min_date and max_date:
            date_range = {"start": min_date, "end": max_date}

    return DashboardStats(
        total_properties=total_properties,
        total_assessed=total_assessed,
        damage_distribution=damage_distribution,
        average_confidence=round(avg_confidence, 3) if avg_confidence else None,
        assessment_date_range=date_range,
    )
