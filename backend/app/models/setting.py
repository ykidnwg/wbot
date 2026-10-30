"""Settings model for system-wide configuration."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(20), default="string")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Default settings keys and their initial values
DEFAULT_SETTINGS: dict[str, dict[str, str]] = {
    "generation_kill_switch": {
        "value": "false",
        "value_type": "boolean",
        "description": "Emergency stop for all AI generation jobs",
    },
    "publishing_kill_switch": {
        "value": "false",
        "value_type": "boolean",
        "description": "Emergency stop for all publishing jobs",
    },
    "max_generation_concurrency": {
        "value": "3",
        "value_type": "integer",
        "description": "Maximum concurrent AI generation jobs",
    },
    "max_publishing_concurrency": {
        "value": "2",
        "value_type": "integer",
        "description": "Maximum concurrent publishing jobs",
    },
    "max_retry_attempts": {
        "value": "5",
        "value_type": "integer",
        "description": "Maximum retry attempts for failed jobs",
    },
    "daily_generation_budget_usd": {
        "value": "50.00",
        "value_type": "float",
        "description": "Maximum daily spend on AI generation in USD",
    },
    "monthly_generation_budget_usd": {
        "value": "500.00",
        "value_type": "float",
        "description": "Maximum monthly spend on AI generation in USD",
    },
    "default_timezone": {
        "value": "Asia/Jakarta",
        "value_type": "string",
        "description": "Default IANA timezone for scheduling",
    },
    "rate_limit_login_per_minute": {
        "value": "10",
        "value_type": "integer",
        "description": "Max login attempts per IP per minute",
    },
    "rate_limit_api_per_minute": {
        "value": "120",
        "value_type": "integer",
        "description": "Max API requests per user per minute",
    },
}
