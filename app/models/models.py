import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, ForeignKey,
    Text, Enum as SAEnum, Boolean, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.core.database import Base


# ─── Enums ───────────────────────────────────────────────

class DamageClass(str, enum.Enum):
    NO_DAMAGE = "no_damage"
    MINOR = "minor_damage"
    MAJOR = "major_damage"
    DESTROYED = "destroyed"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── Property ────────────────────────────────────────────

class Property(Base):
    __tablename__ = "properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(255), unique=True, index=True, nullable=True)
    address = Column(String(500), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location = Column(Geometry("POINT", srid=4326), nullable=True)
    city = Column(String(255), nullable=True)
    state = Column(String(100), nullable=True)
    zip_code = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    images = relationship("Image", back_populates="property", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="property", cascade="all, delete-orphan")
    ground_truth = relationship("GroundTruth", back_populates="property", uselist=False)

    __table_args__ = (
        Index("ix_properties_location", "location", postgresql_using="gist"),
    )


# ─── Image ───────────────────────────────────────────────

class Image(Base):
    __tablename__ = "images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    image_type = Column(String(10), nullable=False)  # "pre" or "post"
    s3_key = Column(String(500), nullable=False)
    s3_bucket = Column(String(255), nullable=False)
    original_filename = Column(String(500), nullable=True)
    file_format = Column(String(10), nullable=True)  # jpeg, png, tiff
    file_size_bytes = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    capture_date = Column(DateTime, nullable=True)
    metadata_json = Column(Text, nullable=True)  # raw EXIF as JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="images")


# ─── Prediction ──────────────────────────────────────────

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    damage_class = Column(SAEnum(DamageClass), nullable=False)
    confidence = Column(Float, nullable=False)
    rationale = Column(Text, nullable=True)
    detected_features = Column(Text, nullable=True)  # JSON list of features
    model_name = Column(String(100), default="gemini-pro-vision")
    model_version = Column(String(50), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("prediction_jobs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="predictions")
    job = relationship("PredictionJob", back_populates="predictions")

    __table_args__ = (
        Index("ix_predictions_damage_class", "damage_class"),
        Index("ix_predictions_confidence", "confidence"),
    )


# ─── Prediction Job ──────────────────────────────────────

class PredictionJob(Base):
    __tablename__ = "prediction_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(SAEnum(JobStatus), default=JobStatus.PENDING)
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    predictions = relationship("Prediction", back_populates="job")


# ─── Ground Truth (FEMA labels) ──────────────────────────

class GroundTruth(Base):
    __tablename__ = "ground_truth"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), unique=True, nullable=False)
    damage_class = Column(SAEnum(DamageClass), nullable=False)
    source = Column(String(100), default="FEMA")
    assessment_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    property = relationship("Property", back_populates="ground_truth")


# ─── User ────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─── Chat Session ────────────────────────────────────────

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    context_used = Column(Text, nullable=True)  # JSON of retrieved context
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")
