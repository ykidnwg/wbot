"""Owner-scoped publishing job inspection and manual retry routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.publishing import PublishingJob
from app.schemas.publishing import (
    PublishingAttemptResponse,
    PublishingJobDetailResponse,
    PublishingJobListResponse,
    PublishingJobResponse,
)
from app.services.audit_log import write_audit_log_from_request
from app.services.publishing import list_job_attempts, list_jobs, retry_job

router = APIRouter(prefix="/publishing/jobs", tags=["publishing"])


@router.get("", response_model=PublishingJobListResponse)
async def get_publishing_jobs(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    status: Annotated[
        str | None,
        Query(
            pattern=(
                "^(queued|running|succeeded|failed|retry_wait|cancelled|"
                "needs_credentials|needs_approval|uncertain)$"
            )
        ),
    ] = None,
) -> PublishingJobListResponse:
    items, total = await list_jobs(
        db_session, current_user.id, page=page, page_size=page_size, status=status
    )
    return PublishingJobListResponse(
        items=[PublishingJobResponse.model_validate(item) for item in items], total=total
    )


@router.get("/{job_id}", response_model=PublishingJobDetailResponse)
async def get_publishing_job(
    job_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> PublishingJobDetailResponse:
    job = await db_session.scalar(
        select(PublishingJob).where(
            PublishingJob.id == job_id, PublishingJob.owner_id == current_user.id
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Publishing job not found")
    attempts = await list_job_attempts(db_session, current_user.id, job.id)
    return PublishingJobDetailResponse(
        **PublishingJobResponse.model_validate(job).model_dump(),
        attempts_detail=[
            PublishingAttemptResponse.model_validate(attempt) for attempt in attempts
        ],
    )


@router.post("/{job_id}/retry", response_model=PublishingJobResponse)
async def post_publishing_retry(
    job_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> PublishingJobResponse:
    try:
        job = await retry_job(db_session, current_user.id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Publishing job not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="publishing_job_retried",
        entity_type="publishing_job",
        entity_id=str(job.id),
        details={"status": job.status},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return PublishingJobResponse.model_validate(job)
