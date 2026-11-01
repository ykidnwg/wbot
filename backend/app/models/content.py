"""Owner-scoped content drafts and immutable generation/approval history."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'retry_wait', 'failed', "
            "'cancelled', 'blocked')",
            name="ck_generation_jobs_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_generation_jobs_attempt_count"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("personas.id", ondelete="RESTRICT"), index=True
    )
    job_type: Mapped[str] = mapped_column(String(40), default="caption", server_default="caption")
    status: Mapped[str] = mapped_column(String(20), default="succeeded", server_default="succeeded")
    provider: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(500))
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    safe_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'generated', 'pending_approval', 'approved', 'rejected', "
            "'scheduled', 'publishing', 'published', 'failed', 'cancelled', 'uncertain')",
            name="ck_content_items_status",
        ),
        CheckConstraint(
            "platform IN ('facebook', 'instagram', 'threads', 'x', 'unassigned')",
            name="ck_content_items_platform",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("personas.id", ondelete="RESTRICT"), index=True
    )
    generation_job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="RESTRICT"), unique=True
    )
    platform: Mapped[str] = mapped_column(
        String(20), default="unassigned", server_default="unassigned"
    )
    topic: Mapped[str] = mapped_column(String(500))
    caption: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(
        String(24), default="draft", server_default="draft", index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ContentVersion(Base):
    __tablename__ = "content_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content_item_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApprovalEvent(Base):
    __tablename__ = "approval_events"
    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected')", name="ck_approval_events_decision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content_item_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    content_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_versions.id", ondelete="RESTRICT")
    )
    decision: Mapped[str] = mapped_column(String(12))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint(
            "mime_type IN ('image/png', 'image/jpeg', 'image/webp')",
            name="ck_media_assets_mime_type",
        ),
        CheckConstraint("size_bytes > 0", name="ck_media_assets_size"),
        CheckConstraint("width > 0 AND height > 0", name="ck_media_assets_dimensions"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("personas.id", ondelete="RESTRICT"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    mime_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(120))
    prompt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
