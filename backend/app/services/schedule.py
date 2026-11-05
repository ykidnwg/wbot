"""Owner-scoped scheduling with idempotency and safe state transitions."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.browser import BrowserAccount
from app.models.content import ContentItem
from app.models.persona import Persona
from app.models.publishing import Schedule
from app.models.social import PersonaAssignment, SocialTarget
from app.schemas.schedule import ScheduleCreateRequest

ACTIVE_SCHEDULE_STATUSES = ("scheduled", "publishing")


async def list_schedules(
    db: AsyncSession,
    owner_id: UUID,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[list[Schedule], int]:
    conditions = [Schedule.owner_id == owner_id]
    if status:
        conditions.append(Schedule.status == status)
    if start:
        conditions.append(Schedule.scheduled_for >= start)
    if end:
        conditions.append(Schedule.scheduled_for <= end)
    base = select(Schedule).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    result = await db.scalars(
        base.order_by(Schedule.scheduled_for.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.all()), total


async def create_schedule(
    db: AsyncSession, owner_id: UUID, payload: ScheduleCreateRequest, *, now: datetime | None = None
) -> Schedule:
    now = now or datetime.now(UTC)
    try:
        timezone = ZoneInfo(payload.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Timezone must be a valid IANA timezone") from exc
    scheduled_for = _as_utc(payload.scheduled_for, timezone)
    if scheduled_for <= now:
        raise ValueError("Scheduled time must be in the future")

    destination_id = payload.social_target_id or payload.browser_account_id
    if destination_id is None:
        raise ValueError("Choose exactly one social target or browser account")
    idempotency_key = payload.idempotency_key or _schedule_key(
        payload.content_item_id, destination_id, scheduled_for
    )
    existing = await db.scalar(
        select(Schedule).where(
            Schedule.owner_id == owner_id,
            Schedule.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing

    item = await db.scalar(
        select(ContentItem)
        .where(ContentItem.id == payload.content_item_id, ContentItem.owner_id == owner_id)
        .with_for_update()
    )
    if item is None:
        raise ValueError("Content item not found")
    if item.status != "approved":
        raise ValueError("Only approved content can be scheduled")

    target: SocialTarget | None = None
    browser_account: BrowserAccount | None = None
    if payload.social_target_id is not None:
        target = await db.scalar(
            select(SocialTarget).where(
                SocialTarget.id == payload.social_target_id,
                SocialTarget.owner_id == owner_id,
            )
        )
        if target is None:
            raise ValueError("Social target not found")
        if target.status != "active":
            raise ValueError("Social target is not active")
        assignment = await db.scalar(
            select(PersonaAssignment).where(
                PersonaAssignment.owner_id == owner_id,
                PersonaAssignment.social_target_id == target.id,
                PersonaAssignment.persona_id == item.persona_id,
                PersonaAssignment.active.is_(True),
            )
        )
        if assignment is None:
            raise ValueError("The content persona is not assigned to this social target")
        if item.platform not in {"unassigned", target.platform}:
            raise ValueError("Content platform does not match the social target")
    else:
        assert payload.browser_account_id is not None
        browser_account = await db.scalar(
            select(BrowserAccount).where(
                BrowserAccount.id == payload.browser_account_id,
                BrowserAccount.owner_id == owner_id,
            )
        )
        if browser_account is None:
            raise ValueError("Browser account not found")
        if browser_account.status != "ACTIVE":
            raise ValueError("Browser account requires manual login first")
        if item.platform not in {"unassigned", browser_account.platform}:
            raise ValueError("Content platform does not match the browser account")

    schedule = Schedule(
        owner_id=owner_id,
        content_item_id=item.id,
        social_target_id=target.id if target is not None else None,
        browser_account_id=browser_account.id if browser_account is not None else None,
        scheduled_for=scheduled_for,
        timezone=payload.timezone,
        status="scheduled",
        idempotency_key=idempotency_key,
    )
    db.add(schedule)
    item.status = "scheduled"
    await db.flush()
    await db.refresh(schedule)
    return schedule


async def cancel_schedule(
    db: AsyncSession, owner_id: UUID, schedule_id: UUID
) -> Schedule | None:
    schedule = await db.scalar(
        select(Schedule)
        .where(Schedule.id == schedule_id, Schedule.owner_id == owner_id)
        .with_for_update()
    )
    if schedule is None:
        return None
    if schedule.status != "scheduled":
        raise ValueError("Only scheduled items can be cancelled")
    schedule.status = "cancelled"
    item = await db.scalar(
        select(ContentItem)
        .where(ContentItem.id == schedule.content_item_id, ContentItem.owner_id == owner_id)
        .with_for_update()
    )
    if item is not None:
        other = await db.scalar(
            select(func.count())
            .select_from(Schedule)
            .where(
                Schedule.owner_id == owner_id,
                Schedule.content_item_id == item.id,
                Schedule.status.in_(ACTIVE_SCHEDULE_STATUSES),
                Schedule.id != schedule.id,
            )
        )
        item.status = "scheduled" if other else "approved"
    await db.flush()
    await db.refresh(schedule)
    return schedule


async def get_owned_schedule(
    db: AsyncSession, owner_id: UUID, schedule_id: UUID
) -> Schedule | None:
    return await db.scalar(
        select(Schedule).where(Schedule.id == schedule_id, Schedule.owner_id == owner_id)
    )


async def get_schedule_payload(
    db: AsyncSession, schedule: Schedule
) -> tuple[ContentItem, SocialTarget, Persona | None]:
    item = await db.scalar(
        select(ContentItem).where(
            ContentItem.id == schedule.content_item_id,
            ContentItem.owner_id == schedule.owner_id,
        )
    )
    if schedule.social_target_id is None:
        raise ValueError("Schedule does not target a social API account")
    target = await db.scalar(
        select(SocialTarget).where(
            SocialTarget.id == schedule.social_target_id,
            SocialTarget.owner_id == schedule.owner_id,
        )
    )
    persona = None
    if item is not None:
        persona = await db.scalar(
            select(Persona).where(
                Persona.id == item.persona_id, Persona.owner_id == schedule.owner_id
            )
        )
    if item is None or target is None:
        raise ValueError("Schedule references unavailable content or target")
    return item, target, persona


def _schedule_key(content_id: UUID, target_id: UUID, scheduled_for: datetime) -> str:
    raw = f"{content_id}:{target_id}:{scheduled_for.isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _as_utc(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone).astimezone(UTC)
    return value.astimezone(UTC)
