"""Notification API routes."""

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.notification import (
    NotificationListResponse,
    NotificationMarkRead,
    NotificationResponse,
)
from app.services.notification import list_notifications, mark_notifications_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    current_user: CurrentUser,
    db_session: DbSession,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
) -> NotificationListResponse:
    """List notifications for the current user."""
    items, unread_count = await list_notifications(
        db_session,
        current_user.id,
        unread_only=unread_only,
        limit=limit,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(i) for i in items],
        unread_count=unread_count,
    )


@router.post("/mark-read", status_code=204)
async def mark_read(
    body: NotificationMarkRead,
    current_user: CurrentUser,
    db_session: DbSession,
) -> None:
    """Mark specific notifications as read."""
    await mark_notifications_read(db_session, current_user.id, body.notification_ids)
    await db_session.commit()
