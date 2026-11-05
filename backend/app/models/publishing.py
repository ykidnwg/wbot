"""Owner-scoped schedules, publishing jobs, and attempts."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEDULE_STATUSES = ("scheduled", "cancelled", "publishing", "published", "failed", "uncertain")
JOB_STATUSES = (
    "queued",
    "running",
    "succeeded",
    "failed",
    "retry_wait",
    "cancelled",
    "needs_credentials",
    "needs_approval",
    "uncertain",
)
ERROR_CATEGORIES = (
    "validation",
    "auth",
    "permission",
    "quota",
    "moderation",
    "rate_limit",
    "temporary",
    "network",
    "unknown",
)


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'cancelled', 'publishing', 'published', "
            "'failed', 'uncertain')",
            name="ck_schedules_status",
        ),
        CheckConstraint(
            "(social_target_id IS NOT NULL AND browser_account_id IS NULL) "
            "OR (social_target_id IS NULL AND browser_account_id IS NOT NULL)",
            name="ck_schedules_one_destination",
        ),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_schedules_owner_idempotency"),
        Index("ix_schedules_due", "status", "scheduled_for"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    content_item_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    social_target_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("social_targets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    browser_account_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("browser_accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", server_default="scheduled"
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PublishingJob(Base):
    __tablename__ = "publishing_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'retry_wait', "
            "'cancelled', 'needs_credentials', 'needs_approval', 'uncertain')",
            name="ck_publishing_jobs_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_publishing_jobs_attempts"),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_publishing_jobs_owner_idempotency"
        ),
        Index("ix_publishing_jobs_due", "status", "next_retry_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    schedule_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content_item_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    social_target_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("social_targets.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    idempotency_key: Mapped[str] = mapped_column(String(128))
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PublishingAttempt(Base):
    __tablename__ = "publishing_attempts"
    __table_args__ = (
        UniqueConstraint("publishing_job_id", "attempt_no", name="uq_publishing_attempts_number"),
        CheckConstraint(
            "status IN ('succeeded', 'failed', 'uncertain', 'rate_limited')",
            name="ck_publishing_attempts_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    publishing_job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("publishing_jobs.id", ondelete="CASCADE"), index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
