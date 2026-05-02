"""SQLAlchemy ORM models for GestPro."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Forest(Base):
    __tablename__ = "forests"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    region: Mapped[str] = mapped_column(String(255), nullable=False)
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lng: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    forest_id: Mapped[str] = mapped_column(String, ForeignKey("forests.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="satellite")
    status: Mapped[str] = mapped_column(String(32), default="detectee", index=True)
    history: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    forest_id: Mapped[str] = mapped_column(String, ForeignKey("forests.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id: Mapped[str | None] = mapped_column(String, nullable=True)
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="manuel")  # manuel | kobo
    kobo_submission_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class DroneMission(Base):
    __tablename__ = "drone_missions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    forest_id: Mapped[str] = mapped_column(String, ForeignKey("forests.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pilot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    planned_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_lat: Mapped[float] = mapped_column(Float, nullable=False)
    target_lng: Mapped[float] = mapped_column(Float, nullable=False)
    radius_m: Mapped[float] = mapped_column(Float, default=500)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="planifiee")
    notes: Mapped[str] = mapped_column(Text, default="")
    ndvi_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class KoboSubmission(Base):
    """Raw Kobo Toolbox webhook submissions, plus mapped result."""
    __tablename__ = "kobo_submissions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    kobo_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    form_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    form_type: Mapped[str] = mapped_column(String(64), default="observation")  # observation | verification | infraction
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Extracted fields
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Linkage to GestPro entities
    forest_id: Mapped[str | None] = mapped_column(String, nullable=True)
    alert_id: Mapped[str | None] = mapped_column(String, nullable=True)
    observation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
