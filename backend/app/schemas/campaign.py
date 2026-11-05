"""Campaign and tracked-link contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

PLATFORM_PATTERN = "^(facebook|instagram|threads|x|multi)$"
STATUS_PATTERN = "^(draft|active|paused|ended|archived)$"


class CampaignCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    persona_id: UUID | None = None
    description: str | None = Field(default=None, max_length=4000)
    platform: str = Field(default="multi", pattern=PLATFORM_PATTERN)
    destination_url: str | None = Field(default=None, max_length=2000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CampaignStatusRequest(BaseModel):
    status: str = Field(pattern=STATUS_PATTERN)


class CampaignResponse(BaseModel):
    id: UUID
    persona_id: UUID | None
    name: str
    description: str | None
    platform: str
    destination_url: str | None
    status: str
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    total: int


class CampaignLinkCreateRequest(BaseModel):
    label: str = Field(min_length=2, max_length=160)
    affiliate_url: str = Field(min_length=8, max_length=2000)
    utm_source: str | None = Field(default=None, max_length=160)
    utm_medium: str | None = Field(default=None, max_length=160)
    utm_campaign: str | None = Field(default=None, max_length=160)
    utm_term: str | None = Field(default=None, max_length=160)
    utm_content: str | None = Field(default=None, max_length=160)


class CampaignLinkResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    label: str
    affiliate_url: str
    tracking_id: str
    tracking_path: str
    destination_url: str
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    utm_term: str | None
    utm_content: str | None
    created_at: datetime
