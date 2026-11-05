"""Publishing-job response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PublishingAttemptResponse(BaseModel):
    id: UUID
    attempt_no: int
    status: str
    http_status: int | None
    error_category: str | None
    error_summary: str | None
    external_post_id: str | None
    started_at: datetime
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PublishingJobResponse(BaseModel):
    id: UUID
    schedule_id: UUID | None
    content_item_id: UUID
    social_target_id: UUID
    platform: str
    status: str
    attempts: int
    external_post_id: str | None
    published_url: str | None
    error_category: str | None
    error_summary: str | None
    next_retry_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PublishingJobListResponse(BaseModel):
    items: list[PublishingJobResponse]
    total: int


class PublishingJobDetailResponse(PublishingJobResponse):
    attempts_detail: list[PublishingAttemptResponse]
