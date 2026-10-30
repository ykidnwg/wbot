"""Content factory request and response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CaptionGenerationRequest(BaseModel):
    persona_id: UUID
    topic: str = Field(min_length=3, max_length=500)
    platform: str = Field(
        default="unassigned", pattern="^(facebook|instagram|threads|x|unassigned)$"
    )


class ContentItemResponse(BaseModel):
    id: UUID
    persona_id: UUID
    generation_job_id: UUID
    platform: str
    topic: str
    caption: str
    provider: str
    status: str
    version_no: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContentListResponse(BaseModel):
    items: list[ContentItemResponse]
    total: int


class ContentApprovalRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str | None = Field(default=None, max_length=2000)


class ContentCaptionUpdateRequest(BaseModel):
    caption: str = Field(min_length=1, max_length=10000)


class ContentVersionResponse(BaseModel):
    id: UUID
    content_item_id: UUID
    version_no: int
    caption: str
    provider: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
