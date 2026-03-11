from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum


# ─── Enums ───────────────────────────────────────────────

class DamageClassEnum(str, Enum):
    NO_DAMAGE = "no_damage"
    MINOR = "minor_damage"
    MAJOR = "major_damage"
    DESTROYED = "destroyed"


class JobStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── Health ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"
    environment: str
    database: str = "connected"


# ─── Property ────────────────────────────────────────────

class PropertyBase(BaseModel):
    address: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class PropertyCreate(PropertyBase):
    external_id: Optional[str] = None


class PropertyResponse(PropertyBase):
    id: UUID
    external_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PropertyDetailResponse(PropertyResponse):
    pre_image_url: Optional[str] = None
    post_image_url: Optional[str] = None
    latest_prediction: Optional["PredictionResponse"] = None
    ground_truth_label: Optional[DamageClassEnum] = None


# ─── Image ───────────────────────────────────────────────

class ImageResponse(BaseModel):
    id: UUID
    property_id: UUID
    image_type: str
    original_filename: Optional[str] = None
    file_format: Optional[str] = None
    file_size_bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    presigned_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class IngestRequest(BaseModel):
    property_id: Optional[str] = Field(None, description="External property identifier")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: Optional[str] = None


class IngestResponse(BaseModel):
    property_id: UUID
    pre_image_id: UUID
    post_image_id: UUID
    message: str = "Images ingested successfully"


# ─── Prediction ──────────────────────────────────────────

class PredictionResult(BaseModel):
    """Schema the ML person's PredictionService must return."""
    damage_class: DamageClassEnum
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: Optional[str] = None
    detected_features: Optional[list[str]] = None
    processing_time_ms: Optional[int] = None


class PredictionResponse(BaseModel):
    id: UUID
    property_id: UUID
    damage_class: DamageClassEnum
    confidence: float
    rationale: Optional[str] = None
    detected_features: Optional[str] = None
    model_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class PredictRequest(BaseModel):
    property_ids: list[UUID] = Field(..., min_length=1, max_length=100)


class PredictBatchResponse(BaseModel):
    job_id: UUID
    total_items: int
    status: JobStatusEnum = JobStatusEnum.PENDING


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatusEnum
    total_items: int
    completed_items: int
    failed_items: int
    created_at: datetime
    completed_at: Optional[datetime] = None


# ─── Results / Query ─────────────────────────────────────

class ResultsQuery(BaseModel):
    damage_level: Optional[DamageClassEnum] = None
    confidence_min: Optional[float] = Field(None, ge=0.0, le=1.0)
    sw_lat: Optional[float] = None
    sw_lng: Optional[float] = None
    ne_lat: Optional[float] = None
    ne_lng: Optional[float] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)


class PaginatedResults(BaseModel):
    items: list[PredictionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── GeoJSON ─────────────────────────────────────────────

class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: dict
    properties: dict


class GeoJSONCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]


# ─── Chat ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    response: str
    session_id: UUID
    context_used: Optional[dict] = None


# ─── Evaluation ──────────────────────────────────────────

class EvaluationMetrics(BaseModel):
    total_predictions: int
    total_ground_truth: int
    matched: int
    overall_accuracy: float
    per_class: dict[str, dict[str, float]]  # {class: {precision, recall, f1}}
    confusion_matrix: dict[str, dict[str, int]]


# ─── Auth ────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ─── Stats ───────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_properties: int
    total_assessed: int
    damage_distribution: dict[str, int]
    average_confidence: Optional[float]
    assessment_date_range: Optional[dict[str, datetime]]


# Forward ref update
PropertyDetailResponse.model_rebuild()
