"""
Evaluation Router (BE-019, BE-020)
====================================
POST /api/evaluate/import — Upload FEMA labels (CSV or JSON)
GET  /api/evaluate         — Run evaluation, return metrics
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.fema_import import fema_import_service
from app.services.evaluation_service import evaluation_service

router = APIRouter(prefix="/api", tags=["Evaluation"])


@router.post("/evaluate/import")
async def import_ground_truth(
    file: UploadFile = File(..., description="FEMA labels in CSV or JSON format"),
    db: AsyncSession = Depends(get_db),
):
    """
    Import FEMA ground-truth labels from CSV or JSON file.

    **Expected fields:**
    - `property_id` (or `external_id`) — match to existing property
    - `damage_class` (or `damage_level`, `label`) — one of: no_damage, minor, major, destroyed
    - `latitude`, `longitude` (optional) — for GPS proximity matching
    - `assessment_date` (optional) — ISO 8601 format

    Returns import statistics including match rate.
    """
    file_data = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".json"):
        result = await fema_import_service.import_json(file_data, db)
    elif filename.endswith(".csv"):
        result = await fema_import_service.import_csv(file_data, db)
    else:
        raise HTTPException(
            status_code=422,
            detail="File must be .csv or .json"
        )

    return result


@router.get("/evaluate")
async def evaluate(db: AsyncSession = Depends(get_db)):
    """
    Run model evaluation against FEMA ground-truth labels.

    Returns:
    - **overall_accuracy**: Fraction of correct predictions
    - **per_class**: Precision, recall, F1, support per damage class
    - **confusion_matrix**: Predicted vs actual counts
    - **matched**: Number of predictions with corresponding ground truth
    """
    return await evaluation_service.evaluate(db)
