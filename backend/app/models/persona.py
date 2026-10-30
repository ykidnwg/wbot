"""Owner-scoped fictional adult persona profiles and immutable approval snapshots."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Persona(Base):
    __tablename__ = "personas"
    __table_args__ = (
        CheckConstraint("age >= 18 AND age <= 120", name="ck_personas_adult_age"),
        CheckConstraint("status IN ('draft', 'approved', 'archived')", name="ck_personas_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(80))
    personality: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[str] = mapped_column(Text)
    clothing_style: Mapped[str] = mapped_column(Text)
    identity_description: Mapped[str] = mapped_column(Text)
    caption_preferences: Mapped[dict[str, object]] = mapped_column(JSON)
    image_provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str] = mapped_column(
        String(80), default="persona-v1", server_default="persona-v1"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PersonaVersion(Base):
    __tablename__ = "persona_versions"
    __table_args__ = (
        UniqueConstraint("persona_id", "version_no", name="uq_persona_versions_number"),
        CheckConstraint("age >= 18 AND age <= 120", name="ck_persona_versions_adult_age"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(80))
    personality: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[str] = mapped_column(Text)
    clothing_style: Mapped[str] = mapped_column(Text)
    identity_description: Mapped[str] = mapped_column(Text)
    caption_preferences: Mapped[dict[str, object]] = mapped_column(JSON)
    image_provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(80))
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PersonaBatch(Base):
    __tablename__ = "persona_batches"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'completed')", name="ck_persona_batches_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PersonaCandidate(Base):
    __tablename__ = "persona_candidates"
    __table_args__ = (
        CheckConstraint("age >= 18 AND age <= 120", name="ck_persona_candidates_adult_age"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'rejected')", name="ck_persona_candidates_status"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    batch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("persona_batches.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )
    target_label: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(80))
    personality: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[str] = mapped_column(Text)
    clothing_style: Mapped[str] = mapped_column(Text)
    identity_description: Mapped[str] = mapped_column(Text)
    caption_preferences: Mapped[dict[str, object]] = mapped_column(JSON)
    image_provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(80), server_default="persona-v1")
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
