"""Schedule request and response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScheduleCreateRequest(BaseModel):
    content_item_id: UUID
    social_target_id: UUID | None = None
    browser_account_id: UUID | None = None
    scheduled_for: datetime
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_destination(self) -> "ScheduleCreateRequest":
        if (self.social_target_id is None) == (self.browser_account_id is None):
            raise ValueError("Choose exactly one social target or browser account")
        return self


class ScheduleResponse(BaseModel):
    id: UUID
    content_item_id: UUID
    social_target_id: UUID | None
    browser_account_id: UUID | None
    scheduled_for: datetime
    timezone: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse]
    total: int
