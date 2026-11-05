"""Owner-scoped browser accounts, encrypted profiles, jobs, events, and workers."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
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

BROWSER_PLATFORMS = ("facebook", "instagram", "threads", "x")
BROWSER_ACCOUNT_STATUSES = (
    "ACTIVE",
    "NEEDS_LOGIN",
    "NEEDS_REAUTHENTICATION",
    "DISABLED",
    "ERROR",
)
BROWSER_SESSION_STATUSES = ("UNKNOWN", "HEALTHY", "NEEDS_LOGIN", "EXPIRED", "ERROR")
BROWSER_JOB_TYPES = ("PUBLISH", "CHECK_SESSION", "LOGIN")
BROWSER_JOB_STATUSES = (
    "QUEUED",
    "RUNNING",
    "SUCCESS",
    "FAILED",
    "NEEDS_USER_ACTION",
    "UNKNOWN",
    "CANCELLED",
)
BROWSER_EVENT_LEVELS = ("INFO", "WARNING", "ERROR")
BROWSER_WORKER_STATUSES = ("ONLINE", "IDLE", "BUSY", "OFFLINE", "ERROR")


class BrowserAccount(Base):
    __tablename__ = "browser_accounts"
    __table_args__ = (
        CheckConstraint(
            "platform IN ('facebook', 'instagram', 'threads', 'x')",
            name="ck_browser_accounts_platform",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'NEEDS_LOGIN', 'NEEDS_REAUTHENTICATION', "
            "'DISABLED', 'ERROR')",
            name="ck_browser_accounts_status",
        ),
        CheckConstraint(
            "session_status IN ('UNKNOWN', 'HEALTHY', 'NEEDS_LOGIN', 'EXPIRED', 'ERROR')",
            name="ck_browser_accounts_session_status",
        ),
        Index("ix_browser_accounts_owner_platform", "owner_id", "platform"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(255))
    handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="NEEDS_LOGIN", server_default="NEEDS_LOGIN"
    )
    session_status: Mapped[str] = mapped_column(
        String(30), default="UNKNOWN", server_default="UNKNOWN"
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_check_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BrowserProfile(Base):
    __tablename__ = "browser_profiles"
    __table_args__ = (UniqueConstraint("account_id", name="uq_browser_profiles_account"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("browser_accounts.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    encrypted_storage_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    state_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BrowserJob(Base):
    __tablename__ = "browser_jobs"
    __table_args__ = (
        CheckConstraint("job_type IN ('PUBLISH', 'CHECK_SESSION', 'LOGIN')", name="ck_browser_jobs_type"),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'SUCCESS', 'FAILED', "
            "'NEEDS_USER_ACTION', 'UNKNOWN', 'CANCELLED')",
            name="ck_browser_jobs_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_browser_jobs_attempts"),
        UniqueConstraint("owner_id", "idempotency_key", name="uq_browser_jobs_owner_idempotency"),
        Index("ix_browser_jobs_due", "status", "next_retry_at"),
        Index("ix_browser_jobs_account_status", "account_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("browser_accounts.id", ondelete="RESTRICT"), index=True
    )
    schedule_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content_item_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", server_default="QUEUED")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    idempotency_key: Mapped[str] = mapped_column(String(128))
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BrowserEvent(Base):
    __tablename__ = "browser_events"
    __table_args__ = (
        CheckConstraint("level IN ('INFO', 'WARNING', 'ERROR')", name="ck_browser_events_level"),
        Index("ix_browser_events_job_created", "browser_job_id", "created_at"),
        Index("ix_browser_events_account_created", "account_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("browser_accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    browser_job_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("browser_jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(60))
    level: Mapped[str] = mapped_column(String(20), default="INFO", server_default="INFO")
    message: Mapped[str] = mapped_column(Text)
    data_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BrowserWorker(Base):
    __tablename__ = "browser_workers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ONLINE', 'IDLE', 'BUSY', 'OFFLINE', 'ERROR')",
            name="ck_browser_workers_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="ONLINE", server_default="ONLINE")
    current_job_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
