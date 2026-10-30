"""Validation and response models for adult personas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonaPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=18, le=120)
    language: str = Field(min_length=2, max_length=80)
    personality: str = Field(min_length=1, max_length=4000)
    target_audience: str = Field(min_length=1, max_length=2000)
    clothing_style: str = Field(min_length=1, max_length=2000)
    identity_description: str = Field(min_length=1, max_length=4000)
    caption_preferences: dict[str, object] = Field(default_factory=dict)
    image_provider: str | None = Field(default=None, max_length=120)
    image_model: str | None = Field(default=None, max_length=120)
    prompt_version: str = Field(default="persona-v1", min_length=1, max_length=80)


class PersonaCreate(PersonaPayload):
    pass


class PersonaResponse(PersonaPayload):
    id: UUID
    owner_id: UUID
    status: str
    version_no: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonaVersionResponse(PersonaPayload):
    id: UUID
    persona_id: UUID
    version_no: int
    approved_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonaListResponse(BaseModel):
    items: list[PersonaResponse]
    total: int
