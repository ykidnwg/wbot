"""Browser job execution cycle with safe, explicit outcomes."""

import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.browser.adapters import BrowserAdapter, BrowserOutcome
from app.browser.runtime import BrowserRuntime
from app.core.config import get_settings
from app.models.browser import BrowserAccount, BrowserJob
from app.models.content import ContentItem, MediaAsset
from app.services.browser import (
    MAX_ATTEMPTS,
    RETRY_BASE_SECONDS,
    claim_due_browser_jobs,
    dispatch_due_browser_schedules,
    list_browser_workers,
    load_browser_session_state,
    mark_job_result,
    record_worker_heartbeat,
    recover_stale_browser_jobs,
    save_browser_session_state,
)
from app.services.media import ObjectStorage

logger = logging.getLogger(__name__)


@dataclass
class BrowserWorkerResult:
    recovered: int = 0
    dispatched: int = 0
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    needs_user_action: int = 0
    unknown: int = 0
    skipped: int = 0


async def run_browser_worker_cycle(
    db: AsyncSession,
    *,
    runtime: BrowserRuntime,
    adapters: dict[str, BrowserAdapter],
    worker_id: str = "browser-worker",
    now: datetime | None = None,
) -> BrowserWorkerResult:
    now = now or datetime.now(UTC)
    settings = get_settings()
    result = BrowserWorkerResult()
    result.recovered = await recover_stale_browser_jobs(db, now=now)
    result.dispatched = await dispatch_due_browser_schedules(db, now=now)
    await record_worker_heartbeat(db, worker_id, status="IDLE", now=now)
    await db.commit()

    try:
        await runtime.start()
    except Exception:
        logger.exception("Browser runtime could not start")
        await record_worker_heartbeat(
            db,
            worker_id,
            status="ERROR",
            metadata={"error": "runtime_start_failed"},
            now=now,
        )
        await db.commit()
        return result

    jobs = await claim_due_browser_jobs(db, now=now, worker_id=worker_id)
    await record_worker_heartbeat(
        db,
        worker_id,
        status="BUSY" if jobs else "IDLE",
        current_job_id=jobs[0].id if jobs else None,
        now=now,
    )
    await db.commit()

    try:
        for job in jobs:
            result.attempted += 1
            job_id = job.id
            job_type = job.job_type
            try:
                await _process_claimed_job(
                    db,
                    job,
                    runtime=runtime,
                    adapters=adapters,
                    settings=settings,
                    now=now,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("Browser job %s failed unexpectedly", job_id)
                try:
                    await _mark_unexpected_failure(db, job_id, job_type, now=now)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    logger.exception("Could not record browser job failure %s", job_id)
                if job_type == "PUBLISH":
                    result.unknown += 1
                else:
                    result.failed += 1
                continue
            if job.status == "SUCCESS":
                result.succeeded += 1
            elif job.status == "NEEDS_USER_ACTION":
                result.needs_user_action += 1
            elif job.status == "UNKNOWN":
                result.unknown += 1
            elif job.status == "FAILED":
                result.failed += 1
    finally:
        try:
            await runtime.close()
        except Exception:
            logger.exception("Browser runtime could not close cleanly")
        await record_worker_heartbeat(db, worker_id, status="IDLE", now=now)
        await db.commit()
    return result


async def _process_claimed_job(
    db: AsyncSession,
    job: BrowserJob,
    *,
    runtime: BrowserRuntime,
    adapters: dict[str, BrowserAdapter],
    settings: Any,
    now: datetime,
) -> None:
    account = await db.scalar(
        select(BrowserAccount).where(
            BrowserAccount.id == job.account_id, BrowserAccount.owner_id == job.owner_id
        )
    )
    if account is None:
        await _finish(
            db,
            job,
            BrowserOutcome("FAILED", "Browser account no longer exists", error_category="validation"),
            now=now,
        )
        return
    if account.status == "DISABLED":
        await _finish(
            db,
            job,
            BrowserOutcome("FAILED", "Browser account is disabled", error_category="permission"),
            now=now,
        )
        return
    adapter = adapters.get(account.platform)
    if adapter is None:
        await _finish(
            db,
            job,
            BrowserOutcome(
                "FAILED",
                f"No browser adapter is configured for {account.platform}",
                error_category="validation",
            ),
            now=now,
        )
        return

    item: ContentItem | None = None
    media_path: str | None = None
    if job.job_type == "PUBLISH":
        if job.content_item_id is None:
            await _finish(
                db,
                job,
                BrowserOutcome("FAILED", "Publishing job has no content", error_category="validation"),
                now=now,
            )
            return
        item = await db.scalar(
            select(ContentItem).where(
                ContentItem.id == job.content_item_id,
                ContentItem.owner_id == job.owner_id,
            )
        )
        if item is None:
            await _finish(
                db,
                job,
                BrowserOutcome("FAILED", "Content no longer exists", error_category="validation"),
                now=now,
            )
            return
        if item.status not in {"approved", "scheduled", "publishing"}:
            await _finish(
                db,
                job,
                BrowserOutcome(
                    "FAILED",
                    "Content is no longer approved for publishing",
                    error_category="validation",
                ),
                now=now,
            )
            return

    storage_state: dict[str, Any] | None = None
    if job.job_type in {"PUBLISH", "CHECK_SESSION"}:
        try:
            storage_state = await load_browser_session_state(
                db,
                job.owner_id,
                account.id,
                encoded_key=settings.token_encryption_key,
            )
        except ValueError:
            await _account_needs_intervention(
                db,
                account,
                "The saved browser session could not be decrypted.",
                now,
            )
            await _finish(
                db,
                job,
                BrowserOutcome(
                    "NEEDS_USER_ACTION",
                    "The saved browser session could not be decrypted. Log in again.",
                    error_category="auth",
                ),
                now=now,
            )
            return
        if storage_state is None:
            await _account_needs_intervention(
                db,
                account,
                "No browser session is saved.",
                now,
            )
            await _finish(
                db,
                job,
                BrowserOutcome(
                    "NEEDS_USER_ACTION",
                    "Manual login is required before this account can run.",
                    error_category="auth",
                ),
                now=now,
            )
            return

    if job.job_type == "LOGIN" and settings.browser_headless:
        await _finish(
            db,
            job,
            BrowserOutcome(
                "NEEDS_USER_ACTION",
                "Visible browser mode is disabled. Set BROWSER_HEADLESS=false for manual login.",
                error_category="auth",
            ),
            now=now,
        )
        return

    if item is not None and item.media_asset_id is not None:
        try:
            media_path = await _materialize_media(db, item, settings)
        except (FileNotFoundError, ValueError):
            await _finish(
                db,
                job,
                BrowserOutcome(
                    "FAILED",
                    "Attached media is unavailable",
                    error_category="temporary",
                    retryable=True,
                ),
                now=now,
            )
            return

    session = None
    try:
        session = await runtime.new_session(storage_state=storage_state)
        if job.job_type == "LOGIN":
            outcome = await adapter.login(
                session,
                account=account,
                timeout_seconds=float(settings.browser_login_timeout_seconds),
            )
            if outcome.status == "SUCCESS":
                profile = await save_browser_session_state(
                    db,
                    job.owner_id,
                    account.id,
                    await session.storage_state(),
                    encoded_key=settings.token_encryption_key,
                    now=now,
                )
                await _finish(
                    db,
                    job,
                    outcome,
                    now=now,
                    result={"state_version": profile.state_version},
                )
                return
        elif job.job_type == "CHECK_SESSION":
            outcome = await adapter.check_session(
                session,
                account=account,
                target_url=_target_url(account),
            )
            await _apply_check_outcome(db, job, account, outcome, now=now)
            return
        else:
            assert item is not None
            outcome = await adapter.publish(
                session,
                account=account,
                caption=item.caption,
                media_path=media_path,
                target_url=_target_url(account),
            )
        await _finish(db, job, outcome, now=now)
    finally:
        if session is not None:
            await session.close()
        if media_path:
            try:
                os.unlink(media_path)
            except OSError:
                pass


async def _apply_check_outcome(
    db: AsyncSession,
    job: BrowserJob,
    account: BrowserAccount,
    outcome: BrowserOutcome,
    *,
    now: datetime,
) -> None:
    if outcome.status == "SUCCESS":
        account.status = "ACTIVE"
        account.session_status = "HEALTHY"
        account.last_checked_at = now
        account.last_check_message = outcome.message
    elif outcome.status == "NEEDS_USER_ACTION":
        account.status = "NEEDS_REAUTHENTICATION"
        account.session_status = "NEEDS_LOGIN"
        account.last_checked_at = now
        account.last_check_message = outcome.message
    elif outcome.status == "FAILED":
        account.status = "ERROR"
        account.session_status = "ERROR"
        account.last_checked_at = now
        account.last_check_message = outcome.message
    await _finish(db, job, outcome, now=now)


async def _finish(
    db: AsyncSession,
    job: BrowserJob,
    outcome: BrowserOutcome,
    *,
    now: datetime,
    result: dict[str, object] | None = None,
) -> None:
    if outcome.status == "SUCCESS":
        await mark_job_result(
            db,
            job,
            status="SUCCESS",
            now=now,
            message=outcome.message,
            external_post_id=outcome.external_post_id,
            published_url=outcome.published_url,
            result=result,
        )
        return
    if outcome.status == "UNKNOWN":
        await mark_job_result(
            db,
            job,
            status="UNKNOWN",
            now=now,
            message=outcome.message,
            error_category=outcome.error_category or "uncertain",
            result=result,
        )
        return
    if outcome.status == "NEEDS_USER_ACTION":
        account = await db.get(BrowserAccount, job.account_id)
        if account is not None and job.job_type != "CHECK_SESSION":
            account.status = "NEEDS_REAUTHENTICATION"
            account.session_status = "NEEDS_LOGIN"
            account.last_checked_at = now
            account.last_check_message = outcome.message
        await mark_job_result(
            db,
            job,
            status="NEEDS_USER_ACTION",
            now=now,
            message=outcome.message,
            error_category=outcome.error_category or "auth",
            result=result,
        )
        return
    retryable = outcome.retryable and job.attempts < MAX_ATTEMPTS
    if retryable:
        await mark_job_result(
            db,
            job,
            status="QUEUED",
            now=now,
            message=outcome.message,
            error_category=outcome.error_category,
            result=result,
            retry_after_seconds=RETRY_BASE_SECONDS * (2 ** (job.attempts - 1)),
        )
        return
    if outcome.error_category == "auth":
        account = await db.get(BrowserAccount, job.account_id)
        if account is not None:
            account.status = "NEEDS_REAUTHENTICATION"
            account.session_status = "NEEDS_LOGIN"
            account.last_checked_at = now
            account.last_check_message = outcome.message
    await mark_job_result(
        db,
        job,
        status="FAILED",
        now=now,
        message=outcome.message,
        error_category=outcome.error_category,
        result=result,
    )


async def _account_needs_intervention(
    db: AsyncSession, account: BrowserAccount, message: str, now: datetime
) -> None:
    account.status = "NEEDS_REAUTHENTICATION"
    account.session_status = "NEEDS_LOGIN"
    account.last_checked_at = now
    account.last_check_message = message
    await db.flush()


async def _mark_unexpected_failure(
    db: AsyncSession, job_id: UUID, job_type: str, *, now: datetime
) -> None:
    job = await db.get(BrowserJob, job_id)
    if job is None:
        return
    status = "UNKNOWN" if job_type == "PUBLISH" else "FAILED"
    await mark_job_result(
        db,
        job,
        status=status,
        now=now,
        message=(
            "The browser worker stopped unexpectedly during publishing. "
            "Verify the platform before retrying."
            if status == "UNKNOWN"
            else "The browser worker stopped unexpectedly."
        ),
        error_category="uncertain" if status == "UNKNOWN" else "unknown",
    )


async def _materialize_media(
    db: AsyncSession, item: ContentItem, settings: Any
) -> str:
    assert item.media_asset_id is not None
    asset = await db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == item.media_asset_id,
            MediaAsset.owner_id == item.owner_id,
        )
    )
    if asset is None:
        raise ValueError("Attached media is unavailable")
    storage = ObjectStorage(Path(settings.media_storage_root))
    data = storage.get(asset.storage_key)
    suffix = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(asset.mime_type, ".bin")
    handle, path = tempfile.mkstemp(prefix="wbot-media-", suffix=suffix)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(data)
    except Exception:
        os.unlink(path)
        raise
    return path


def _target_url(account: BrowserAccount) -> str | None:
    value = account.metadata_json.get("target_url") if account.metadata_json else None
    return value if isinstance(value, str) and value else None


def worker_health(db_workers: list[Any], *, now: datetime | None = None) -> list[dict[str, object]]:
    now = now or datetime.now(UTC)
    health: list[dict[str, object]] = []
    for worker in db_workers:
        stale = worker.last_heartbeat_at <= now - timedelta(minutes=2)
        health.append(
            {
                "id": worker.id,
                "status": "OFFLINE" if stale else worker.status,
                "current_job_id": worker.current_job_id,
                "last_heartbeat_at": worker.last_heartbeat_at,
            }
        )
    return health


async def list_worker_health(db: AsyncSession, *, now: datetime | None = None) -> list[dict[str, object]]:
    workers = await list_browser_workers(db)
    return worker_health(workers, now=now)
