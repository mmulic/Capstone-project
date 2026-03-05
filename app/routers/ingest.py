"""
Data Ingestion Router (BE-006)
===============================
POST /api/ingest — Upload a single pre/post image pair
Validates format, extracts EXIF/GPS, preprocesses, stores in S3 + DB.
"""

import json
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.elements import WKTElement

from app.core.database import get_db
from app.models.models import Property, Image
from app.services.s3_service import s3_service
from app.services.image_preprocessor import image_preprocessor
from app.schemas.schemas import IngestResponse

router = APIRouter(prefix="/api", tags=["Data Ingestion"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_images(
    pre_image: UploadFile = File(..., description="Pre-disaster aerial image"),
    post_image: UploadFile = File(..., description="Post-disaster aerial image"),
    latitude: float = Form(..., ge=-90, le=90),
    longitude: float = Form(..., ge=-180, le=180),
    address: str = Form(default=None),
    external_id: str = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and preprocess a pre/post disaster image pair.

    Pipeline:
    1. Validate both images (format, size, integrity)
    2. Extract EXIF metadata (GPS, capture date, camera info)
    3. Normalize dimensions and apply histogram equalization
    4. Upload preprocessed images to S3
    5. Create property + image records in database
    """
    image_records = []

    for img_file, img_type in [(pre_image, "pre"), (post_image, "post")]:
        file_data = await img_file.read()

        errors = image_preprocessor.validate_file(
            file_data, img_file.content_type or "image/jpeg", img_file.filename or ""
        )
        if errors:
            raise HTTPException(
                status_code=422,
                detail=f"{img_type}_image validation failed: {'; '.join(errors)}",
            )

        metadata = image_preprocessor.extract_metadata(file_data)

        preprocessed = await image_preprocessor.preprocess(
            file_data, img_file.content_type or "image/jpeg", img_file.filename or ""
        )

        image_records.append({
            "type": img_type,
            "data": preprocessed.data,
            "original_filename": img_file.filename,
            "content_type": preprocessed.content_type,
            "metadata": metadata,
        })

    # Use EXIF GPS if caller passed 0,0
    for rec in image_records:
        meta = rec["metadata"]
        if meta.latitude and meta.longitude and latitude == 0 and longitude == 0:
            latitude = meta.latitude
            longitude = meta.longitude
            break

    prop = Property(
        external_id=external_id,
        address=address,
        latitude=latitude,
        longitude=longitude,
        location=WKTElement(f"POINT({longitude} {latitude})", srid=4326),
    )
    db.add(prop)
    await db.flush()

    db_images = []
    for rec in image_records:
        s3_key = await s3_service.upload_file(
            file_data=rec["data"],
            prefix=f"images/{prop.id}/{rec['type']}",
            filename=rec["original_filename"] or f"{rec['type']}.jpg",
            content_type=rec["content_type"],
        )

        meta = rec["metadata"]
        db_image = Image(
            property_id=prop.id,
            image_type=rec["type"],
            s3_key=s3_key,
            s3_bucket=s3_service.bucket,
            original_filename=rec["original_filename"],
            file_format=meta.file_format.lower() if meta.file_format else None,
            file_size_bytes=meta.file_size_bytes,
            width=meta.width,
            height=meta.height,
            capture_date=meta.capture_date,
            metadata_json=json.dumps(meta.raw_exif) if meta.raw_exif else None,
        )
        db.add(db_image)
        db_images.append(db_image)

    await db.flush()

    return IngestResponse(
        property_id=prop.id,
        pre_image_id=db_images[0].id,
        post_image_id=db_images[1].id,
        message=f"Images ingested and preprocessed. Normalized to {db_images[0].width}x{db_images[0].height}px.",
    )
