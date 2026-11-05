"""Browser account, session, job, event, and worker contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrowserAccountCreate(BaseModel):
    platform: Literal["facebook", "instagram", "threads", "x"]
    display_name: str = Field(min_length=1, max_length=255)
    handle: str | None = Field(default=None, max_length=255)
    profile_image_url: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, object] = Field(default_factory=dict)


class BrowserAccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    handle: str | None = Field(default=None, max_length=255)
    profile_image_url: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, object] | None = None


class BrowserAccountResponse(BaseModel):
    id: UUID
    platform: str
    display_name: str
    handle: str | None
    profile_image_url: str | None
    status: str
    session_status: str
    last_checked_at: datetime | None
    last_check_message: str | None
    last_used_at: datetime | None
    metadata_json: dict[str, object]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrowserAccountListResponse(BaseModel):
    items: list[BrowserAccountResponse]
    total: int


class BrowserJobCreate(BaseModel):
    account_id: UUID
    content_item_id: UUID | None = None
    job_type: Literal["PUBLISH", "CHECK_SESSION", "LOGIN"]
    scheduled_for: datetime | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class BrowserJobResponse(BaseModel):
    id: UUID
    account_id: UUID
    schedule_id: UUID | None
    content_item_id: UUID | None
    job_type: str
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
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrowserJobListResponse(BaseModel):
    items: list[BrowserJobResponse]
    total: int


class BrowserEventResponse(BaseModel):
    id: UUID
    event_type: str
    level: str
    message: str
    data_json: dict[str, object]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrowserJobDetailResponse(BrowserJobResponse):
    events: list[BrowserEventResponse]


class BrowserWorkerResponse(BaseModel):
    id: str
    status: str
    current_job_id: UUID | None
    last_heartbeat_at: datetime
    metadata_json: dict[str, object]

    model_config = ConfigDict(from_attributes=True)


class BrowserWorkerListResponse(BaseModel):
    items: list[BrowserWorkerResponse]
    total: int


class BrowserActivityListResponse(BaseModel):
    items: list[BrowserEventResponse]
    total: int
