"""Media API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImageGenerationRequest(BaseModel):
    persona_id: UUID
    prompt: str = Field(min_length=3, max_length=4000)
    aspect_ratio: str = Field(
        default="square", pattern="^(square|portrait|vertical|landscape)$"
    )


class MediaAssetResponse(BaseModel):
    id: UUID
    persona_id: UUID
    mime_type: str
    size_bytes: int
    width: int
    height: int
    checksum: str
    provider: str
    model: str
    prompt: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MediaAssetListResponse(BaseModel):
    items: list[MediaAssetResponse]
    total: int


class ProviderStatusResponse(BaseModel):
    provider: str
    model: str
    mode: str
    health: str
