"""
Results Router (BE-013, BE-014)
================================
GET /api/results          — Query damage assessments with filters + pagination
GET /api/properties/{id}  — Full property detail with images + prediction
"""

import math
from uuid import UUID
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_MakeEnvelope, ST_Within

from app.core.database import get_db
from app.models.models import Property, Image, Prediction, GroundTruth, DamageClass
from app.services.s3_service import s3_service
from app.schemas.schemas import (
    PredictionResponse, PaginatedResults, PropertyDetailResponse,
    DamageClassEnum,
)

router = APIRouter(prefix="/api", tags=["Results"])


@router.get("/results", response_model=PaginatedResults)
async def get_results(
    damage_level: Optional[str] = Query(None, description="Filter: no_damage, minor_damage, major_damage, destroyed"),
    confidence_min: Optional[float] = Query(None, ge=0.0, le=1.0),
    sw_lat: Optional[float] = Query(None, description="Bounding box SW latitude"),
    sw_lng: Optional[float] = Query(None, description="Bounding box SW longitude"),
    ne_lat: Optional[float] = Query(None, description="Bounding box NE latitude"),
    ne_lng: Optional[float] = Query(None, description="Bounding box NE longitude"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    Query damage assessment results with filtering and pagination.

    Filters:
    - **damage_level**: FEMA damage classification
    - **confidence_min**: Minimum prediction confidence (0.0–1.0)
    - **sw_lat/sw_lng/ne_lat/ne_lng**: Bounding box (PostGIS spatial query)
    - **date_from/date_to**: Prediction date range
    - **page/page_size**: Pagination controls
    """
    # Base query — predictions joined with properties
    query = (
        select(Prediction)
        .join(Property, Prediction.property_id == Property.id)
        .order_by(desc(Prediction.created_at))
    )

    count_query = (
        select(func.count(Prediction.id))
        .join(Property, Prediction.property_id == Property.id)
    )

    # Apply filters
    filters = []

    if damage_level:
        try:
            damage_enum = DamageClass(damage_level)
            filters.append(Prediction.damage_class == damage_enum)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid damage_level '{damage_level}'. Valid: no_damage, minor_damage, major_damage, destroyed"
            )

    if confidence_min is not None:
        filters.append(Prediction.confidence >= confidence_min)

    if date_from:
        filters.append(Prediction.created_at >= date_from)

    if date_to:
        filters.append(Prediction.created_at <= date_to)

    # Bounding box filter via PostGIS
    if all(v is not None for v in [sw_lat, sw_lng, ne_lat, ne_lng]):
        bbox = ST_MakeEnvelope(sw_lng, sw_lat, ne_lng, ne_lat, 4326)
        filters.append(ST_Within(Property.location, bbox))

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    predictions = result.scalars().all()

    items = [
        PredictionResponse(
            id=p.id,
            property_id=p.property_id,
            damage_class=p.damage_class,
            confidence=p.confidence,
            rationale=p.rationale,
            detected_features=p.detected_features,
            model_name=p.model_name,
            created_at=p.created_at,
        )
        for p in predictions
    ]

    return PaginatedResults(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/properties/{property_id}", response_model=PropertyDetailResponse)
async def get_property_detail(
    property_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full detail for a single property including:
    - Property metadata (address, coordinates)
    - Pre/post image URLs (presigned S3 links)
    - Latest prediction (damage class, confidence, rationale)
    - FEMA ground-truth label (if available)
    """
    prop = await db.get(Property, property_id)
    if not prop:
        raise HTTPException(status_code=404, detail=f"Property {property_id} not found")

    # Fetch images
    images_result = await db.execute(
        select(Image).where(Image.property_id == property_id)
    )
    images = images_result.scalars().all()

    pre_img = next((i for i in images if i.image_type == "pre"), None)
    post_img = next((i for i in images if i.image_type == "post"), None)

    # Generate presigned URLs
    pre_url = None
    post_url = None
    if pre_img:
        pre_url = await s3_service.generate_presigned_url(pre_img.s3_key)
    if post_img:
        post_url = await s3_service.generate_presigned_url(post_img.s3_key)

    # Get latest prediction
    pred_result = await db.execute(
        select(Prediction)
        .where(Prediction.property_id == property_id)
        .order_by(desc(Prediction.created_at))
        .limit(1)
    )
    latest_pred = pred_result.scalar_one_or_none()

    # Get ground truth
    gt_result = await db.execute(
        select(GroundTruth).where(GroundTruth.property_id == property_id)
    )
    ground_truth = gt_result.scalar_one_or_none()

    return PropertyDetailResponse(
        id=prop.id,
        external_id=prop.external_id,
        address=prop.address,
        latitude=prop.latitude,
        longitude=prop.longitude,
        city=prop.city,
        state=prop.state,
        zip_code=prop.zip_code,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
        pre_image_url=pre_url,
        post_image_url=post_url,
        latest_prediction=PredictionResponse(
            id=latest_pred.id,
            property_id=latest_pred.property_id,
            damage_class=latest_pred.damage_class,
            confidence=latest_pred.confidence,
            rationale=latest_pred.rationale,
            detected_features=latest_pred.detected_features,
            model_name=latest_pred.model_name,
            created_at=latest_pred.created_at,
        ) if latest_pred else None,
        ground_truth_label=DamageClassEnum(ground_truth.damage_class.value) if ground_truth else None,
    )
