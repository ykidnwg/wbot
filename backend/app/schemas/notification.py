"""Pydantic schemas for notifications."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: UUID
    level: str
    title: str
    message: str
    is_read: bool
    entity_type: str | None
    entity_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class NotificationMarkRead(BaseModel):
    notification_ids: list[UUID]
