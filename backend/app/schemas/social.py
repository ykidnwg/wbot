"""Social account and persona assignment API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProviderStatusResponse(BaseModel):
    provider: str
    status: str
    graph_api_version: str
    required_permissions: list[str]


class OAuthStartResponse(BaseModel):
    authorization_url: str
    expires_at: datetime


class SocialConnectionResponse(BaseModel):
    id: UUID
    platform: str
    external_account_id: str
    display_name: str
    status: str
    token_expires_at: datetime | None
    last_synced_at: datetime | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class SocialTargetResponse(BaseModel):
    id: UUID
    connection_id: UUID
    platform: str
    external_target_id: str
    display_name: str
    username: str | None
    profile_image_url: str | None
    status: str
    last_synced_at: datetime | None
    assigned_persona_id: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PersonaAssignmentRequest(BaseModel):
    persona_id: UUID


class PersonaAssignmentResponse(BaseModel):
    id: UUID
    persona_id: UUID
    social_target_id: UUID
    active: bool
    assigned_at: datetime
    removed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SocialListResponse(BaseModel):
    items: list[SocialConnectionResponse]
    total: int


class TargetListResponse(BaseModel):
    items: list[SocialTargetResponse]
    total: int


class CallbackErrorResponse(BaseModel):
    detail: str = Field(description="Safe OAuth error message")
