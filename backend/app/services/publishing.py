"""Due-schedule dispatch and durable publishing-job execution."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.content import ContentItem, MediaAsset
from app.models.publishing import PublishingAttempt, PublishingJob, Schedule
from app.models.social import SocialTarget
from app.providers.publishing import FacebookPagePublisher, Publisher, PublishingError
from app.services.media import ObjectStorage
from app.services.social import meta_config
from app.services.social_security import decrypt_token

logger = logging.getLogger(__name__)
settings = get_settings()

MAX_ATTEMPTS = 3
RETRY_BASE_SECONDS = 60
STALE_JOB_SECONDS = 15 * 60


@dataclass
class WorkerResult:
    dispatched: int = 0
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    recovered: int = 0
    skipped: int = 0


async def recover_stale_jobs(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 20
) -> int:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(seconds=STALE_JOB_SECONDS)
    jobs = (
        await db.scalars(
            select(PublishingJob)
            .where(
                PublishingJob.status == "running",
                PublishingJob.started_at.is_not(None),
                PublishingJob.started_at <= cutoff,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for job in jobs:
        job.status = "uncertain"
        job.error_category = "uncertain"
        job.error_summary = (
            "Worker stopped while publishing; verify the platform before retrying"
        )
        job.finished_at = now
        await _record_attempt(
            db,
            job,
            "uncertain",
            None,
            "uncertain",
            job.error_summary,
            now,
        )
        await _set_schedule(db, job, "uncertain", now)
        item = await db.scalar(
            select(ContentItem).where(
                ContentItem.id == job.content_item_id,
                ContentItem.owner_id == job.owner_id,
            )
        )
        if item is not None:
            _set_content(item, "uncertain")
    await db.flush()
    return len(jobs)


async def dispatch_due_schedules(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 20
) -> int:
    now = now or datetime.now(UTC)
    schedules = (
        await db.scalars(
            select(Schedule)
            .where(
                Schedule.status == "scheduled",
                Schedule.browser_account_id.is_(None),
                Schedule.scheduled_for <= now,
            )
            .order_by(Schedule.scheduled_for.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    dispatched = 0
    for schedule in schedules:
        existing = await db.scalar(
            select(PublishingJob).where(
                PublishingJob.owner_id == schedule.owner_id,
                PublishingJob.idempotency_key == f"schedule:{schedule.id}",
            )
        )
        if existing is None:
            assert schedule.social_target_id is not None
            target = await db.scalar(
                select(SocialTarget).where(
                    SocialTarget.id == schedule.social_target_id,
                    SocialTarget.owner_id == schedule.owner_id,
                )
            )
            if target is None:
                schedule.status = "failed"
                continue
            db.add(
                PublishingJob(
                    owner_id=schedule.owner_id,
                    schedule_id=schedule.id,
                    content_item_id=schedule.content_item_id,
                    social_target_id=schedule.social_target_id,
                    platform=target.platform,
                    status="queued",
                    idempotency_key=f"schedule:{schedule.id}",
                )
            )
            schedule.status = "publishing"
            item = await db.scalar(
                select(ContentItem).where(
                    ContentItem.id == schedule.content_item_id,
                    ContentItem.owner_id == schedule.owner_id,
                )
            )
            if item is not None and item.status == "scheduled":
                item.status = "publishing"
        dispatched += 1
    await db.flush()
    return dispatched


async def claim_due_jobs(
    db: AsyncSession, *, now: datetime | None = None, limit: int = 10
) -> list[PublishingJob]:
    now = now or datetime.now(UTC)
    jobs = (
        await db.scalars(
            select(PublishingJob)
            .where(
                PublishingJob.status.in_(("queued", "retry_wait")),
                or_(PublishingJob.next_retry_at.is_(None), PublishingJob.next_retry_at <= now),
            )
            .order_by(PublishingJob.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    claimed: list[PublishingJob] = []
    for job in jobs:
        job.status = "running"
        job.started_at = now
        job.finished_at = None
        job.attempts += 1
        claimed.append(job)
    await db.flush()
    return claimed


async def process_claim(
    db: AsyncSession, job: PublishingJob, *, now: datetime | None = None
) -> None:
    now = now or datetime.now(UTC)
    item = await db.scalar(
        select(ContentItem).where(
            ContentItem.id == job.content_item_id, ContentItem.owner_id == job.owner_id
        )
    )
    target = await db.scalar(
        select(SocialTarget).where(
            SocialTarget.id == job.social_target_id, SocialTarget.owner_id == job.owner_id
        )
    )
    if item is None or target is None:
        await _fail_job(db, job, "validation", "Content or social target no longer exists", now)
        return
    if target.status != "active":
        await _fail_job(db, job, "permission", "Social target is not active", now)
        return
    if item.status not in {"approved", "scheduled", "publishing"}:
        await _fail_job(db, job, "validation", "Content is no longer approved for publishing", now)
        return
    if job.platform != "facebook":
        await _fail_job(db, job, "validation", "No publisher is configured for this platform", now)
        return

    config = meta_config(settings)
    if config is None or not settings.token_encryption_key:
        await _set_needs_credentials(
            db, job, "NEEDS_CREDENTIALS: Meta publishing credentials are not configured", now
        )
        return
    try:
        access_token = decrypt_token(
            target.encrypted_access_token, settings.token_encryption_key
        )
    except (ValueError, TypeError):
        await _set_needs_credentials(
            db, job, "NEEDS_CREDENTIALS: reconnect the Facebook Page", now
        )
        return

    image_data = None
    image_mime_type = None
    if item.media_asset_id is not None:
        asset = await db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == item.media_asset_id, MediaAsset.owner_id == job.owner_id
            )
        )
        if asset is None:
            await _fail_job(db, job, "validation", "Attached media is unavailable", now)
            return
        try:
            storage = ObjectStorage(Path(settings.media_storage_root))
            image_data = storage.get(asset.storage_key)
            image_mime_type = asset.mime_type
        except (FileNotFoundError, ValueError):
            await _fail_job(db, job, "temporary", "Media storage is unavailable", now)
            return

    publisher: Publisher = FacebookPagePublisher(config)
    try:
        result = await publisher.publish(
            external_target_id=target.external_target_id,
            access_token=access_token,
            caption=item.caption,
            image_data=image_data,
            image_mime_type=image_mime_type,
        )
    except PublishingError as exc:
        await _record_attempt(db, job, "failed", None, exc.category, exc.safe_message, now)
        if exc.uncertain:
            job.status = "uncertain"
            job.error_category = exc.category
            job.error_summary = exc.safe_message
            job.finished_at = now
            await _set_schedule(db, job, "uncertain", now)
            _set_content(item, "uncertain")
            return
        await _retry_or_fail(db, job, item, exc.category, exc.safe_message, now)
        return

    job.status = "succeeded"
    job.external_post_id = result.external_post_id
    job.published_url = result.published_url
    job.error_category = None
    job.error_summary = None
    job.next_retry_at = None
    job.finished_at = now
    await _record_attempt(
        db, job, "succeeded", 200, None, None, now, result.external_post_id
    )
    await _set_schedule(db, job, "published", now)
    _set_content(item, "published")
    await db.flush()


async def _retry_or_fail(
    db: AsyncSession,
    job: PublishingJob,
    item: ContentItem,
    category: str,
    summary: str,
    now: datetime,
) -> None:
    retryable = category in {"rate_limit", "temporary", "network"}
    if retryable and job.attempts < MAX_ATTEMPTS:
        delay = RETRY_BASE_SECONDS * (2 ** (job.attempts - 1))
        job.status = "retry_wait"
        job.error_category = category
        job.error_summary = summary
        job.next_retry_at = now + timedelta(seconds=delay)
        await _set_schedule(db, job, "publishing", now)
        _set_content(item, "publishing")
    else:
        job.status = "failed"
        job.error_category = category
        job.error_summary = summary
        job.finished_at = now
        await _set_schedule(db, job, "failed", now)
        _set_content(item, "failed")
    await db.flush()


async def _fail_job(
    db: AsyncSession, job: PublishingJob, category: str, summary: str, now: datetime
) -> None:
    job.status = "failed"
    job.error_category = category
    job.error_summary = summary
    job.finished_at = now
    await _record_attempt(db, job, "failed", None, category, summary, now)
    await _set_schedule(db, job, "failed", now)
    item = await db.scalar(
        select(ContentItem).where(
            ContentItem.id == job.content_item_id, ContentItem.owner_id == job.owner_id
        )
    )
    if item is not None:
        _set_content(item, "failed")
    await db.flush()


async def _set_needs_credentials(
    db: AsyncSession, job: PublishingJob, summary: str, now: datetime
) -> None:
    job.status = "needs_credentials"
    job.error_category = "auth"
    job.error_summary = summary
    job.finished_at = now
    await _record_attempt(db, job, "failed", None, "auth", summary, now)
    await _set_schedule(db, job, "failed", now)
    item = await db.scalar(
        select(ContentItem).where(
            ContentItem.id == job.content_item_id, ContentItem.owner_id == job.owner_id
        )
    )
    if item is not None:
        _set_content(item, "approved")
    await db.flush()


async def _record_attempt(
    db: AsyncSession,
    job: PublishingJob,
    status: str,
    http_status: int | None,
    category: str | None,
    summary: str | None,
    now: datetime,
    external_post_id: str | None = None,
) -> None:
    db.add(
        PublishingAttempt(
            owner_id=job.owner_id,
            publishing_job_id=job.id,
            attempt_no=job.attempts,
            status="rate_limited" if category == "rate_limit" else status,
            http_status=http_status,
            error_category=category,
            error_summary=summary,
            external_post_id=external_post_id,
            finished_at=now,
        )
    )


async def _set_schedule(
    db: AsyncSession, job: PublishingJob, status: str, now: datetime
) -> None:
    if job.schedule_id is None:
        return
    schedule = await db.get(Schedule, job.schedule_id)
    if schedule is None:
        return
    schedule.status = status
    schedule.updated_at = now


def _set_content(item: ContentItem, status: str) -> None:
    item.status = status


async def list_jobs(
    db: AsyncSession,
    owner_id: UUID,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
) -> tuple[list[PublishingJob], int]:
    conditions = [PublishingJob.owner_id == owner_id]
    if status:
        conditions.append(PublishingJob.status == status)
    base = select(PublishingJob).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    jobs = await db.scalars(
        base.order_by(PublishingJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(jobs.all()), total


async def list_job_attempts(
    db: AsyncSession, owner_id: UUID, job_id: UUID
) -> list[PublishingAttempt]:
    result = await db.scalars(
        select(PublishingAttempt)
        .where(
            PublishingAttempt.owner_id == owner_id,
            PublishingAttempt.publishing_job_id == job_id,
        )
        .order_by(PublishingAttempt.attempt_no.asc())
    )
    return list(result.all())


async def run_worker_cycle(db: AsyncSession, *, now: datetime | None = None) -> WorkerResult:
    now = now or datetime.now(UTC)
    result = WorkerResult()
    result.recovered = await recover_stale_jobs(db, now=now)
    result.dispatched = await dispatch_due_schedules(db, now=now)
    jobs = await claim_due_jobs(db, now=now)
    await db.commit()

    for job in jobs:
        result.attempted += 1
        try:
            await process_claim(db, job, now=now)
            await db.commit()
            if job.status == "succeeded":
                result.succeeded += 1
            elif job.status in {"failed", "uncertain", "needs_credentials"}:
                result.failed += 1
        except Exception:
            await db.rollback()
            logger.exception("Publishing job %s failed unexpectedly", job.id)
            result.failed += 1
    return result


async def retry_job(
    db: AsyncSession, owner_id: UUID, job_id: UUID, *, now: datetime | None = None
) -> PublishingJob | None:
    now = now or datetime.now(UTC)
    job = await db.scalar(
        select(PublishingJob)
        .where(PublishingJob.id == job_id, PublishingJob.owner_id == owner_id)
        .with_for_update()
    )
    if job is None:
        return None
    if job.status not in {"failed", "needs_credentials"}:
        raise ValueError("Only failed or credential-blocked jobs can be retried")
    job.status = "queued"
    job.next_retry_at = None
    job.error_category = None
    job.error_summary = None
    job.finished_at = None
    await _set_schedule(db, job, "publishing", now)
    item = await db.scalar(
        select(ContentItem).where(
            ContentItem.id == job.content_item_id, ContentItem.owner_id == owner_id
        )
    )
    if item is not None:
        item.status = "publishing"
    await db.flush()
    await db.refresh(job)
    return job