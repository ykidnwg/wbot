"""Service layer for notifications."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


async def create_notification(
    db: AsyncSession,
    *,
    owner_id: UUID,
    title: str,
    message: str,
    level: str = "info",
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> Notification:
    """Create a new notification for a user."""
    notification = Notification(
        owner_id=owner_id,
        level=level,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(notification)
    await db.flush()
    return notification


async def list_notifications(
    db: AsyncSession,
    owner_id: UUID,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> tuple[list[Notification], int]:
    """List notifications for a user, returning items and unread count."""
    query = select(Notification).where(Notification.owner_id == owner_id)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    query = query.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.scalars(query)
    items = list(result.all())

    unread_count = (
        await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.owner_id == owner_id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )
    return items, unread_count


async def mark_notifications_read(
    db: AsyncSession,
    owner_id: UUID,
    notification_ids: list[UUID],
) -> int:
    """Mark specific notifications as read. Returns count of updated rows."""
    result = await db.scalars(
        update(Notification)
        .where(
            Notification.owner_id == owner_id,
            Notification.id.in_(notification_ids),
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
        .returning(Notification.id)
    )
    await db.flush()
    return len(result.all())
