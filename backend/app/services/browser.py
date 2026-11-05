"""Owner-scoped browser account, profile, job, event, and worker services."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.models.browser import (
    BROWSER_JOB_STATUSES,
    BROWSER_JOB_TYPES,
    BrowserAccount,
    BrowserEvent,
    BrowserJob,
    BrowserProfile,
    BrowserWorker,
)
from app.models.content import ContentItem
from app.models.publishing import Schedule
from app.services.social_security import decrypt_token, encrypt_token

STALE_JOB_SECONDS = 15 * 60
RETRY_BASE_SECONDS = 60
MAX_ATTEMPTS = 3


async def create_browser_account(
    db: AsyncSession,
    owner_id: UUID,
    *,
    platform: str,
    display_name: str,
    handle: str | None = None,
    profile_image_url: str | None = None,
    metadata: dict[str, object] | None = None,
) -> BrowserAccount:
    account = BrowserAccount(
        owner_id=owner_id,
        platform=platform,
        display_name=display_name,
        handle=handle,
        profile_image_url=profile_image_url,
        status="NEEDS_LOGIN",
        session_status="UNKNOWN",
        metadata_json=metadata or {},
    )
    db.add(account)
    await db.flush()
    db.add(
        BrowserProfile(
            owner_id=owner_id,
            account_id=account.id,
            name=display_name,
        )
    )
    await _append_event(
        db,
        owner_id=owner_id,
        account_id=account.id,
        event_type="ACCOUNT_CREATED",
        message="Browser account created. Manual login is required.",
    )
    await db.flush()
    await db.refresh(account)
    return account


async def list_browser_accounts(
    db: AsyncSession,
    owner_id: UUID,
    *,
    page: int = 1,
    page_size: int = 100,
    status: str | None = None,
) -> tuple[list[BrowserAccount], int]:
    conditions = [BrowserAccount.owner_id == owner_id]
    if status:
        conditions.append(BrowserAccount.status == status)
    base = select(BrowserAccount).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await db.scalars(
        base.order_by(BrowserAccount.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.all()), total


async def get_browser_account(
    db: AsyncSession, owner_id: UUID, account_id: UUID
) -> BrowserAccount | None:
    return await db.scalar(
        select(BrowserAccount).where(
            BrowserAccount.id == account_id, BrowserAccount.owner_id == owner_id
        )
    )


async def update_browser_account(
    db: AsyncSession,
    owner_id: UUID,
    account_id: UUID,
    *,
    display_name: str | None = None,
    handle: str | None = None,
    profile_image_url: str | None = None,
    metadata: dict[str, object] | None = None,
) -> BrowserAccount | None:
    account = await db.scalar(
        select(BrowserAccount)
        .where(BrowserAccount.id == account_id, BrowserAccount.owner_id == owner_id)
        .with_for_update()
    )
    if account is None:
        return None
    if display_name is not None:
        account.display_name = display_name
    if handle is not None:
        account.handle = handle
    if profile_image_url is not None:
        account.profile_image_url = profile_image_url
    if metadata is not None:
        account.metadata_json = metadata
    await db.flush()
    await db.refresh(account)
    return account


async def save_browser_session_state(
    db: AsyncSession,
    owner_id: UUID,
    account_id: UUID,
    storage_state: dict[str, Any],
    *,
    encoded_key: str | None = None,
    now: datetime | None = None,
) -> BrowserProfile:
    now = now or datetime.now(UTC)
    key = encoded_key or get_settings().token_encryption_key
    if not key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is not configured")
    _validate_storage_state(storage_state)
    account = await db.scalar(
        select(BrowserAccount)
        .where(BrowserAccount.id == account_id, BrowserAccount.owner_id == owner_id)
        .with_for_update()
    )
    if account is None:
        raise ValueError("Browser account not found")
    profile = await db.scalar(
        select(BrowserProfile)
        .where(
            BrowserProfile.account_id == account.id,
            BrowserProfile.owner_id == owner_id,
        )
        .with_for_update()
    )
    if profile is None:
        raise ValueError("Browser profile not found")
    profile.encrypted_storage_state = encrypt_token(
        json.dumps(storage_state, separators=(",", ":")), key
    )
    profile.state_version += 1
    profile.state_updated_at = now
    profile.last_used_at = now
    account.status = "ACTIVE"
    account.session_status = "HEALTHY"
    account.last_checked_at = now
    account.last_check_message = "Manual browser session captured"
    account.last_used_at = now
    await _append_event(
        db,
        owner_id=owner_id,
        account_id=account.id,
        event_type="SESSION_UPDATED",
        message="Encrypted browser session state saved.",
        data={"state_version": profile.state_version},
    )
    await db.flush()
    await db.refresh(profile)
    return profile


async def load_browser_session_state(
    db: AsyncSession,
    owner_id: UUID,
    account_id: UUID,
    *,
    encoded_key: str | None = None,
) -> dict[str, Any] | None:
    key = encoded_key or get_settings().token_encryption_key
    if not key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is not configured")
    profile = await db.scalar(
        select(BrowserProfile).where(
            BrowserProfile.account_id == account_id,
            BrowserProfile.owner_id == owner_id,
        )
    )
    if profile is None or not profile.encrypted_storage_state:
        return None
    try:
        payload = json.loads(decrypt_token(profile.encrypted_storage_state, key))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Browser session state cannot be decrypted") from exc
    if not isinstance(payload, dict):
        raise ValueError("Browser session state is invalid")
    return payload


async def clear_browser_session_state(
    db: AsyncSession,
    owner_id: UUID,
    account_id: UUID,
    *,
    now: datetime | None = None,
) -> BrowserProfile | None:
    now = now or datetime.now(UTC)
    account = await get_browser_account(db, owner_id, account_id)
    if account is None:
        return None
    profile = await db.scalar(
        select(BrowserProfile)
        .where(
            BrowserProfile.account_id == account.id,
            BrowserProfile.owner_id == owner_id,
        )
        .with_for_update()
    )
    if profile is None:
        return None
    profile.encrypted_storage_state = None
    profile.state_version += 1
    profile.state_updated_at = now
    account.status = "NEEDS_LOGIN"
    account.session_status = "UNKNOWN"
    account.last_checked_at = now
    account.last_check_message = "Session cleared by operator"
    await _append_event(
        db,
        owner_id=owner_id,
        account_id=account.id,
        event_type="SESSION_CLEARED",
        level="WARNING",
        message="Browser session state cleared. Manual login is required again.",
    )
    await db.flush()
    await db.refresh(profile)
    return profile


async def create_browser_job(
    db: AsyncSession,
    owner_id: UUID,
    *,
    account_id: UUID,
    job_type: str,
    content_item_id: UUID | None = None,
    schedule_id: UUID | None = None,
    idempotency_key: str | None = None,
    scheduled_for: datetime | None = None,
    now: datetime | None = None,
) -> BrowserJob:
    now = now or datetime.now(UTC)
    if job_type not in BROWSER_JOB_TYPES:
        raise ValueError("Unsupported browser job type")
    key = idempotency_key or _job_key(
        job_type, account_id, content_item_id, scheduled_for or now
    )
    existing = await db.scalar(
        select(BrowserJob).where(
            BrowserJob.owner_id == owner_id,
            BrowserJob.idempotency_key == key,
        )
    )
    if existing is not None:
        return existing
    account = await db.scalar(
        select(BrowserAccount).where(
            BrowserAccount.id == account_id, BrowserAccount.owner_id == owner_id
        )
    )
    if account is None:
        raise ValueError("Browser account not found")

    if job_type == "PUBLISH":
        if content_item_id is None:
            raise ValueError("Publishing jobs require approved content")
        item = await db.scalar(
            select(ContentItem)
            .where(ContentItem.id == content_item_id, ContentItem.owner_id == owner_id)
            .with_for_update()
        )
        if item is None:
            raise ValueError("Content item not found")
        if item.status not in {"approved", "scheduled", "publishing", "failed"}:
            raise ValueError("Only approved content can be published")
        if account.status != "ACTIVE":
            raise ValueError("Browser account requires manual login first")
        if item.platform not in {"unassigned", account.platform}:
            raise ValueError("Content platform does not match the browser account")

    job = BrowserJob(
        owner_id=owner_id,
        account_id=account.id,
        schedule_id=schedule_id,
        content_item_id=content_item_id,
        job_type=job_type,
        status="QUEUED",
        idempotency_key=key,
        next_retry_at=scheduled_for if scheduled_for and scheduled_for > now else None,
    )
    db.add(job)
    await db.flush()
    await _append_event(
        db,
        owner_id=owner_id,
        account_id=account.id,
        job_id=job.id,
        event_type="JOB_QUEUED",
        message=f"{job_type} job queued.",
    )
    await db.flush()
    await db.refresh(job)
    return job


async def list_browser_jobs(
    db: AsyncSession,
    owner_id: UUID,
    *,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    account_id: UUID | None = None,
) -> tuple[list[BrowserJob], int]:
    conditions = [BrowserJob.owner_id == owner_id]
    if status:
        conditions.append(BrowserJob.status == status)
    if account_id is not None:
        conditions.append(BrowserJob.account_id == account_id)
    base = select(BrowserJob).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await db.scalars(
        base.order_by(BrowserJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.all()), total


async def get_browser_job(
    db: AsyncSession, owner_id: UUID, job_id: UUID
) -> BrowserJob | None:
    return await db.scalar(
        select(BrowserJob).where(BrowserJob.id == job_id, BrowserJob.owner_id == owner_id)
    )


async def list_browser_events(
    db: AsyncSession, owner_id: UUID, job_id: UUID
) -> list[BrowserEvent]:
    rows = await db.scalars(
        select(BrowserEvent)
        .where(BrowserEvent.owner_id == owner_id, BrowserEvent.browser_job_id == job_id)
        .order_by(BrowserEvent.created_at.asc(), BrowserEvent.id.asc())
    )
    return list(rows.all())


async def list_browser_activity(
    db: AsyncSession,
    owner_id: UUID,
    *,
    limit: int = 100,
    account_id: UUID | None = None,
) -> list[BrowserEvent]:
    conditions = [BrowserEvent.owner_id == owner_id]
    if account_id is not None:
        conditions.append(BrowserEvent.account_id == account_id)
    rows = await db.scalars(
        select(BrowserEvent)
        .where(*conditions)
        .order_by(BrowserEvent.created_at.desc(), BrowserEvent.id.desc())
        .limit(limit)
    )
    return list(rows.all())


async def dispatch_due_browser_schedules(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 20
) -> int:
    now = now or datetime.now(UTC)
    schedules = (
        await db.scalars(
            select(Schedule)
            .where(
                Schedule.status == "scheduled",
                Schedule.browser_account_id.is_not(None),
                Schedule.scheduled_for <= now,
            )
            .order_by(Schedule.scheduled_for.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    dispatched = 0
    for schedule in schedules:
        assert schedule.browser_account_id is not None
        existing = await db.scalar(
            select(BrowserJob).where(
                BrowserJob.owner_id == schedule.owner_id,
                BrowserJob.idempotency_key == f"browser-schedule:{schedule.id}",
            )
        )
        if existing is not None:
            continue
        account = await get_browser_account(db, schedule.owner_id, schedule.browser_account_id)
        item = await db.scalar(
            select(ContentItem)
            .where(
                ContentItem.id == schedule.content_item_id,
                ContentItem.owner_id == schedule.owner_id,
            )
            .with_for_update()
        )
        if account is None or account.status != "ACTIVE" or item is None:
            schedule.status = "failed"
            if item is not None and item.status == "scheduled":
                item.status = "approved"
            await _append_event(
                db,
                owner_id=schedule.owner_id,
                account_id=schedule.browser_account_id,
                event_type="SCHEDULE_BLOCKED",
                level="WARNING",
                message="Scheduled browser job was not queued because the account is unavailable.",
                data={"schedule_id": str(schedule.id)},
            )
            continue
        await create_browser_job(
            db,
            schedule.owner_id,
            account_id=account.id,
            job_type="PUBLISH",
            content_item_id=schedule.content_item_id,
            schedule_id=schedule.id,
            idempotency_key=f"browser-schedule:{schedule.id}",
            now=now,
        )
        schedule.status = "publishing"
        item.status = "publishing"
        dispatched += 1
    await db.flush()
    return dispatched


async def claim_due_browser_jobs(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 10,
    worker_id: str = "browser-worker",
) -> list[BrowserJob]:
    now = now or datetime.now(UTC)
    busy = aliased(BrowserJob)
    busy_running = (
        select(busy.id)
        .where(busy.account_id == BrowserJob.account_id, busy.status == "RUNNING")
        .exists()
    )
    jobs = (
        await db.scalars(
            select(BrowserJob)
            .where(
                BrowserJob.status == "QUEUED",
                or_(BrowserJob.next_retry_at.is_(None), BrowserJob.next_retry_at <= now),
                ~busy_running,
            )
            .order_by(BrowserJob.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    claimed: list[BrowserJob] = []
    for job in jobs:
        job.status = "RUNNING"
        job.attempts += 1
        job.locked_by = worker_id
        job.locked_at = now
        job.started_at = now
        job.finished_at = None
        await _append_event(
            db,
            owner_id=job.owner_id,
            account_id=job.account_id,
            job_id=job.id,
            event_type="JOB_STARTED",
            message=f"Attempt {job.attempts} started.",
        )
        claimed.append(job)
    await db.flush()
    return claimed


async def recover_stale_browser_jobs(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 20
) -> int:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(seconds=STALE_JOB_SECONDS)
    jobs = (
        await db.scalars(
            select(BrowserJob)
            .where(
                BrowserJob.status == "RUNNING",
                BrowserJob.started_at.is_not(None),
                BrowserJob.started_at <= cutoff,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for job in jobs:
        job.status = "UNKNOWN"
        job.error_category = "uncertain"
        job.error_summary = (
            "Browser worker stopped during the job; verify the platform before acting"
        )
        job.finished_at = now
        job.locked_by = None
        await _append_event(
            db,
            owner_id=job.owner_id,
            account_id=job.account_id,
            job_id=job.id,
            event_type="JOB_UNKNOWN",
            level="ERROR",
            message=job.error_summary,
        )
        await _mark_schedule_and_content_uncertain(db, job)
    await db.flush()
    return len(jobs)


async def retry_browser_job(
    db: AsyncSession, owner_id: UUID, job_id: UUID, *, now: datetime | None = None
) -> BrowserJob | None:
    now = now or datetime.now(UTC)
    job = await db.scalar(
        select(BrowserJob)
        .where(BrowserJob.id == job_id, BrowserJob.owner_id == owner_id)
        .with_for_update()
    )
    if job is None:
        return None
    if job.status not in {"FAILED", "NEEDS_USER_ACTION"}:
        raise ValueError("Only failed or intervention-blocked jobs can be retried")
    job.status = "QUEUED"
    job.next_retry_at = None
    job.error_category = None
    job.error_summary = None
    job.locked_by = None
    job.locked_at = None
    job.finished_at = None
    await _append_event(
        db,
        owner_id=owner_id,
        account_id=job.account_id,
        job_id=job.id,
        event_type="JOB_RETRIED",
        message="Operator queued a manual retry.",
    )
    await db.flush()
    await db.refresh(job)
    return job


async def cancel_browser_job(
    db: AsyncSession, owner_id: UUID, job_id: UUID, *, now: datetime | None = None
) -> BrowserJob | None:
    now = now or datetime.now(UTC)
    job = await db.scalar(
        select(BrowserJob)
        .where(BrowserJob.id == job_id, BrowserJob.owner_id == owner_id)
        .with_for_update()
    )
    if job is None:
        return None
    if job.status != "QUEUED":
        raise ValueError("Only queued jobs can be cancelled")
    job.status = "CANCELLED"
    job.finished_at = now
    await _append_event(
        db,
        owner_id=owner_id,
        account_id=job.account_id,
        job_id=job.id,
        event_type="JOB_CANCELLED",
        level="WARNING",
        message="Operator cancelled the queued job.",
    )
    await db.flush()
    await db.refresh(job)
    return job


async def record_worker_heartbeat(
    db: AsyncSession,
    worker_id: str,
    *,
    status: str = "ONLINE",
    current_job_id: UUID | None = None,
    metadata: dict[str, object] | None = None,
    now: datetime | None = None,
) -> BrowserWorker:
    now = now or datetime.now(UTC)
    worker = await db.get(BrowserWorker, worker_id)
    if worker is None:
        worker = BrowserWorker(id=worker_id)
        db.add(worker)
    worker.status = status
    worker.current_job_id = current_job_id
    worker.last_heartbeat_at = now
    worker.metadata_json = metadata or {}
    await db.flush()
    await db.refresh(worker)
    return worker


async def list_browser_workers(db: AsyncSession) -> list[BrowserWorker]:
    rows = await db.scalars(
        select(BrowserWorker).order_by(BrowserWorker.last_heartbeat_at.desc())
    )
    return list(rows.all())


async def mark_job_result(
    db: AsyncSession,
    job: BrowserJob,
    *,
    status: str,
    now: datetime | None = None,
    message: str | None = None,
    error_category: str | None = None,
    external_post_id: str | None = None,
    published_url: str | None = None,
    result: dict[str, object] | None = None,
    retry_after_seconds: int | None = None,
) -> None:
    now = now or datetime.now(UTC)
    if status not in BROWSER_JOB_STATUSES:
        raise ValueError("Unsupported browser job status")
    job.status = status
    job.finished_at = now
    job.error_category = error_category
    job.error_summary = message
    if external_post_id is not None:
        job.external_post_id = external_post_id
    if published_url is not None:
        job.published_url = published_url
    if result is not None:
        job.result_json = result
    if retry_after_seconds is not None and status == "QUEUED":
        job.next_retry_at = now + timedelta(seconds=retry_after_seconds)
        job.finished_at = None
    if status == "RUNNING":
        job.finished_at = None
    if status in {"QUEUED", "SUCCESS", "FAILED", "NEEDS_USER_ACTION", "UNKNOWN", "CANCELLED"}:
        job.locked_by = None
        job.locked_at = None
    level = "INFO"
    if status in {"FAILED", "UNKNOWN"}:
        level = "ERROR"
    elif status in {"NEEDS_USER_ACTION", "QUEUED"}:
        level = "WARNING"
    await _append_event(
        db,
        owner_id=job.owner_id,
        account_id=job.account_id,
        job_id=job.id,
        event_type=f"JOB_{status}",
        level=level,
        message=message or f"Job transitioned to {status}.",
        data=result or {},
    )
    if status == "SUCCESS":
        account = await db.get(BrowserAccount, job.account_id)
        if account is not None:
            account.status = "ACTIVE"
            account.session_status = "HEALTHY"
            account.last_used_at = now
    await _apply_job_status_to_schedule_and_content(db, job, status)
    await db.flush()


async def _apply_job_status_to_schedule_and_content(
    db: AsyncSession, job: BrowserJob, status: str
) -> None:
    content_status: str | None = None
    schedule_status: str | None = None
    if status == "SUCCESS":
        content_status = "published"
        schedule_status = "published"
    elif status == "FAILED":
        content_status = "failed"
        schedule_status = "failed"
    elif status == "NEEDS_USER_ACTION":
        content_status = "approved"
        schedule_status = "failed"
    elif status == "UNKNOWN":
        content_status = "uncertain"
        schedule_status = "uncertain"
    elif status == "QUEUED":
        schedule_status = "publishing"
        content_status = "publishing"
    elif status == "CANCELLED":
        content_status = "approved"
        schedule_status = "cancelled"
    if content_status is not None and job.content_item_id is not None:
        item = await db.scalar(
            select(ContentItem).where(
                ContentItem.id == job.content_item_id,
                ContentItem.owner_id == job.owner_id,
            )
        )
        if item is not None:
            item.status = content_status
    if schedule_status is not None and job.schedule_id is not None:
        schedule = await db.get(Schedule, job.schedule_id)
        if schedule is not None:
            schedule.status = schedule_status


async def _mark_schedule_and_content_uncertain(db: AsyncSession, job: BrowserJob) -> None:
    if job.schedule_id is not None:
        schedule = await db.get(Schedule, job.schedule_id)
        if schedule is not None:
            schedule.status = "uncertain"
    if job.content_item_id is not None:
        item = await db.scalar(
            select(ContentItem).where(
                ContentItem.id == job.content_item_id,
                ContentItem.owner_id == job.owner_id,
            )
        )
        if item is not None:
            item.status = "uncertain"


async def _append_event(
    db: AsyncSession,
    *,
    owner_id: UUID,
    event_type: str,
    message: str,
    account_id: UUID | None = None,
    job_id: UUID | None = None,
    level: str = "INFO",
    data: dict[str, object] | None = None,
) -> BrowserEvent:
    event = BrowserEvent(
        owner_id=owner_id,
        account_id=account_id,
        browser_job_id=job_id,
        event_type=event_type,
        level=level,
        message=message,
        data_json=data or {},
    )
    db.add(event)
    return event


def _job_key(
    job_type: str, account_id: UUID, content_item_id: UUID | None, scheduled_for: datetime
) -> str:
    raw = f"{job_type}:{account_id}:{content_item_id or '-'}:{scheduled_for.isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _validate_storage_state(storage_state: dict[str, Any]) -> None:
    cookies = storage_state.get("cookies")
    origins = storage_state.get("origins")
    if not isinstance(cookies, list) or not isinstance(origins, list):
        raise ValueError("Storage state must contain cookies and origins lists")
    for cookie in cookies:
        if not isinstance(cookie, dict):
            raise ValueError("Storage state cookies are invalid")
    for origin in origins:
        if not isinstance(origin, dict):
            raise ValueError("Storage state origins are invalid")
