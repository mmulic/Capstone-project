"""
Predict Router (BE-012)
========================
POST /api/predict       — Trigger single or batch VLM inference
GET  /api/predict/{job_id} — Poll batch job status
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.prediction_orchestrator import prediction_orchestrator
from app.schemas.schemas import (
    PredictRequest, PredictBatchResponse, PredictionResponse,
    JobStatusResponse, JobStatusEnum,
)

router = APIRouter(prefix="/api", tags=["Predictions"])


@router.post("/predict")
async def predict(
    request: PredictRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger damage prediction for one or more properties.

    - **Single property** (1 ID): Returns prediction result inline
    - **Batch** (2+ IDs): Returns job_id for polling via GET /api/predict/{job_id}

    The backend calls the PredictionService interface (implemented by ML teammate
    with Google Gemini Vision API). Results are stored in the predictions table.
    """
    property_ids = request.property_ids

    if len(property_ids) == 1:
        # Single prediction — return inline
        try:
            prediction = await prediction_orchestrator.predict_single(
                str(property_ids[0]), db
            )
            return PredictionResponse(
                id=prediction.id,
                property_id=prediction.property_id,
                damage_class=prediction.damage_class,
                confidence=prediction.confidence,
                rationale=prediction.rationale,
                detected_features=prediction.detected_features,
                model_name=prediction.model_name,
                created_at=prediction.created_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))

    else:
        # Batch prediction — return job_id
        try:
            job = await prediction_orchestrator.predict_batch(
                [str(pid) for pid in property_ids], db
            )
            return PredictBatchResponse(
                job_id=job.id,
                total_items=job.total_items,
                status=JobStatusEnum.PENDING,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/predict/{job_id}", response_model=JobStatusResponse)
async def get_prediction_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Poll the status of a batch prediction job."""
    job = await prediction_orchestrator.get_job_status(str(job_id), db)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        total_items=job.total_items,
        completed_items=job.completed_items,
        failed_items=job.failed_items,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
