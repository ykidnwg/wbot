"""Pydantic schemas for settings."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SettingResponse(BaseModel):
    id: UUID
    key: str
    value: str
    value_type: str
    description: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str = Field(min_length=1, max_length=2000)


class SettingsListResponse(BaseModel):
    settings: list[SettingResponse]
