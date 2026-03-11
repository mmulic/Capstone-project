"""
Batch Ingest Router (BE-009)
==============================
POST /api/ingest/batch  — Upload ZIP of image pairs, returns job_id
GET  /api/ingest/{job_id}/status — Poll job progress
"""

import io
import uuid
import zipfile
import asyncio
import json
import re
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.elements import WKTElement

from app.core.database import get_db, AsyncSessionLocal
from app.models.models import Property, Image, PredictionJob, JobStatus
from app.services.s3_service import s3_service
from app.services.image_preprocessor import image_preprocessor

router = APIRouter(prefix="/api", tags=["Data Ingestion"])

# In-memory job tracking (production would use Redis or DB)
_batch_jobs: dict[str, dict] = {}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}


def _parse_filename(filename: str) -> Optional[tuple[str, str]]:
    """
    Parse filename to extract property_id and image type.
    Expects format: {property_id}_pre.jpg or {property_id}_post.jpg
    Also supports: pre_{property_id}.jpg, {property_id}/pre.jpg
    """
    name = filename.rsplit("/", 1)[-1]  # get just filename
    name_lower = name.lower()
    stem = name_lower.rsplit(".", 1)[0]

    # Pattern: {id}_pre or {id}_post
    match = re.match(r"^(.+?)_(pre|post)$", stem)
    if match:
        return match.group(1), match.group(2)

    # Pattern: pre_{id} or post_{id}
    match = re.match(r"^(pre|post)_(.+)$", stem)
    if match:
        return match.group(2), match.group(1)

    return None


async def _process_batch(
    job_id: str,
    file_pairs: dict[str, dict[str, bytes]],
    default_lat: float,
    default_lng: float,
):
    """Background task: process all image pairs from a ZIP upload."""
    job = _batch_jobs[job_id]
    job["status"] = "processing"

    async with AsyncSessionLocal() as db:
        try:
            for prop_id, images in file_pairs.items():
                try:
                    pre_data = images.get("pre")
                    post_data = images.get("post")

                    if not pre_data or not post_data:
                        job["failed"] += 1
                        job["errors"].append(f"{prop_id}: missing pre or post image")
                        continue

                    # Preprocess both images
                    pre_processed = await image_preprocessor.preprocess(
                        pre_data, "image/jpeg", f"{prop_id}_pre.jpg"
                    )
                    post_processed = await image_preprocessor.preprocess(
                        post_data, "image/jpeg", f"{prop_id}_post.jpg"
                    )

                    # Use EXIF GPS if available, else default
                    lat = pre_processed.metadata.latitude or default_lat
                    lng = pre_processed.metadata.longitude or default_lng

                    # Create property
                    prop = Property(
                        external_id=prop_id,
                        latitude=lat,
                        longitude=lng,
                        location=WKTElement(f"POINT({lng} {lat})", srid=4326),
                    )
                    db.add(prop)
                    await db.flush()

                    # Upload and record both images
                    for img_data, img_type, processed in [
                        (pre_data, "pre", pre_processed),
                        (post_data, "post", post_processed),
                    ]:
                        s3_key = await s3_service.upload_file(
                            file_data=processed.data,
                            prefix=f"images/{prop.id}/{img_type}",
                            filename=f"{prop_id}_{img_type}.jpg",
                            content_type="image/jpeg",
                        )
                        db.add(Image(
                            property_id=prop.id,
                            image_type=img_type,
                            s3_key=s3_key,
                            s3_bucket=s3_service.bucket,
                            original_filename=f"{prop_id}_{img_type}.jpg",
                            file_format=processed.metadata.file_format.lower(),
                            file_size_bytes=processed.metadata.file_size_bytes,
                            width=processed.metadata.width,
                            height=processed.metadata.height,
                            capture_date=processed.metadata.capture_date,
                        ))

                    job["completed"] += 1

                except Exception as e:
                    job["failed"] += 1
                    job["errors"].append(f"{prop_id}: {str(e)}")

            await db.commit()
            job["status"] = "completed"
            job["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            job["status"] = "failed"
            job["error_message"] = str(e)


@router.post("/ingest/batch")
async def batch_ingest(
    background_tasks: BackgroundTasks,
    zip_file: UploadFile = File(..., description="ZIP containing image pairs named {property_id}_pre.jpg / {property_id}_post.jpg"),
    default_latitude: float = Form(0.0, description="Default latitude if EXIF GPS unavailable"),
    default_longitude: float = Form(0.0, description="Default longitude if EXIF GPS unavailable"),
):
    """
    Upload a ZIP file containing multiple pre/post image pairs.

    **Naming convention:**
    - `{property_id}_pre.jpg` and `{property_id}_post.jpg`
    - Or: `pre_{property_id}.jpg` and `post_{property_id}.jpg`

    Returns a job_id for polling progress via GET /api/ingest/{job_id}/status.
    """
    if not zip_file.filename or not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="File must be a .zip archive")

    zip_data = await zip_file.read()

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_data))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="Invalid or corrupted ZIP file")

    # Parse ZIP contents into property_id -> {pre: bytes, post: bytes}
    file_pairs: dict[str, dict[str, bytes]] = {}

    for entry in zf.namelist():
        if entry.endswith("/"):
            continue

        ext = "." + entry.rsplit(".", 1)[-1].lower() if "." in entry else ""
        if ext not in ALLOWED_EXTENSIONS:
            continue

        parsed = _parse_filename(entry)
        if not parsed:
            continue

        prop_id, img_type = parsed
        if prop_id not in file_pairs:
            file_pairs[prop_id] = {}
        file_pairs[prop_id][img_type] = zf.read(entry)

    if not file_pairs:
        raise HTTPException(
            status_code=422,
            detail="No valid image pairs found. Use naming: {property_id}_pre.jpg / {property_id}_post.jpg",
        )

    # Create job
    job_id = str(uuid.uuid4())
    total_pairs = len(file_pairs)
    complete_pairs = sum(1 for v in file_pairs.values() if "pre" in v and "post" in v)

    _batch_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "total": total_pairs,
        "complete_pairs": complete_pairs,
        "incomplete_pairs": total_pairs - complete_pairs,
        "completed": 0,
        "failed": 0,
        "errors": [],
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "error_message": None,
    }

    # Launch background processing
    background_tasks.add_task(_process_batch, job_id, file_pairs, default_latitude, default_longitude)

    return {
        "job_id": job_id,
        "total_pairs_found": total_pairs,
        "complete_pairs": complete_pairs,
        "incomplete_pairs": total_pairs - complete_pairs,
        "status": "pending",
        "message": f"Processing {complete_pairs} complete image pairs. Poll GET /api/ingest/{job_id}/status for progress.",
    }


@router.get("/ingest/{job_id}/status")
async def batch_ingest_status(job_id: str):
    """Poll the status of a batch ingest job."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "total": job["total"],
        "completed": job["completed"],
        "failed": job["failed"],
        "errors": job["errors"][:10],  # cap at 10 for response size
        "created_at": job["created_at"],
        "completed_at": job["completed_at"],
        "progress_pct": round(
            (job["completed"] + job["failed"]) / max(job["total"], 1) * 100, 1
        ),
    }
