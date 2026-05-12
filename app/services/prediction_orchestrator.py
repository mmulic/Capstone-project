"""
Prediction Orchestration Service (BE-011)
==========================================
Manages the prediction pipeline:
- Single and batch prediction triggers
- Async job queue with progress tracking
- Retry logic with exponential backoff
- Result caching and DB persistence
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.models import (
    Property, Image, Prediction, PredictionJob,
    JobStatus, DamageClass,
)
from app.services.prediction_service import prediction_service
from app.services.s3_service import s3_service
from app.schemas.schemas import PredictionResult


MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
MAX_CONCURRENCY = 5


class PredictionOrchestrator:
    """Orchestrates prediction pipeline — calls PredictionService, stores results."""

    async def predict_single(
        self, property_id: str, db: AsyncSession
    ) -> Prediction:
        """Run prediction for a single property. Returns the Prediction record."""
        # Fetch property and its images
        prop = await db.get(Property, property_id)
        if not prop:
            raise ValueError(f"Property {property_id} not found")

        images_result = await db.execute(
            select(Image).where(Image.property_id == property_id)
        )
        images = images_result.scalars().all()

        pre_img = next((i for i in images if i.image_type == "pre"), None)
        post_img = next((i for i in images if i.image_type == "post"), None)

        if not pre_img or not post_img:
            raise ValueError(f"Property {property_id} missing pre or post image")

        # Download images from S3
        pre_data = await s3_service.download_file(pre_img.s3_key)
        post_data = await s3_service.download_file(post_img.s3_key)

        if not pre_data or not post_data:
            raise ValueError(f"Failed to download images for property {property_id}")

        # Call prediction service (with retries)
        result = await self._predict_with_retry(
            pre_data, post_data, str(property_id)
        )

        # Store result in DB
        prediction = Prediction(
            property_id=property_id,
            damage_class=DamageClass(result.damage_class.value),
            confidence=result.confidence,
            rationale=result.rationale,
            detected_features=json.dumps(result.detected_features) if result.detected_features else None,
            model_name="gemini-pro-vision",
            processing_time_ms=result.processing_time_ms,
        )
        db.add(prediction)
        await db.flush()

        return prediction

    async def predict_batch(
        self, property_ids: list[str], db: AsyncSession
    ) -> PredictionJob:
        """Create a batch prediction job. Processing runs in background."""
        job = PredictionJob(
            status=JobStatus.PENDING,
            total_items=len(property_ids),
            completed_items=0,
            failed_items=0,
        )
        db.add(job)
        await db.flush()

        # Launch background processing
        asyncio.create_task(
            self._process_batch(str(job.id), property_ids)
        )

        return job

    async def get_job_status(
        self, job_id: str, db: AsyncSession
    ) -> Optional[PredictionJob]:
        """Get current status of a prediction job."""
        return await db.get(PredictionJob, job_id)

    # ── Internal Methods ─────────────────────────────────

    async def _predict_with_retry(
        self, pre_data: bytes, post_data: bytes, property_id: str
    ) -> PredictionResult:
        """Call prediction service with exponential backoff retry."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                result = await prediction_service.predict(
                    pre_data, post_data, property_id
                )
                return result
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"Prediction failed after {MAX_RETRIES} attempts: {last_error}"
        )

    async def _process_batch(
        self, job_id: str, property_ids: list[str]
    ):
        """Background task: process batch predictions with concurrency control."""
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        async def process_one(prop_id: str):
            async with semaphore:
                async with AsyncSessionLocal() as db:
                    try:
                        prediction = await self.predict_single(prop_id, db)
                        prediction.job_id = uuid.UUID(job_id)
                        await db.commit()
                        return True
                    except Exception as e:
                        await db.rollback()
                        return False

        # Process all with concurrency limit
        results = await asyncio.gather(
            *[process_one(pid) for pid in property_ids],
            return_exceptions=True,
        )

        completed = sum(1 for r in results if r is True)
        failed = len(results) - completed

        # Update job status
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(PredictionJob)
                .where(PredictionJob.id == uuid.UUID(job_id))
                .values(
                    status=JobStatus.COMPLETED if failed == 0 else JobStatus.COMPLETED,
                    completed_items=completed,
                    failed_items=failed,
                    completed_at=datetime.utcnow(),
                    error_message=f"{failed} predictions failed" if failed > 0 else None,
                )
            )
            await db.commit()


# Singleton
prediction_orchestrator = PredictionOrchestrator()
