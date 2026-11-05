"""Owner-scoped browser account, job, and worker control routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.browser import (
    BrowserAccountCreate,
    BrowserAccountListResponse,
    BrowserAccountResponse,
    BrowserAccountUpdate,
    BrowserActivityListResponse,
    BrowserEventResponse,
    BrowserJobCreate,
    BrowserJobDetailResponse,
    BrowserJobListResponse,
    BrowserJobResponse,
    BrowserWorkerListResponse,
    BrowserWorkerResponse,
)
from app.services.audit_log import write_audit_log_from_request
from app.services.browser import (
    cancel_browser_job,
    clear_browser_session_state,
    create_browser_account,
    create_browser_job,
    get_browser_account,
    get_browser_job,
    list_browser_activity,
    list_browser_accounts,
    list_browser_events,
    list_browser_jobs,
    list_browser_workers,
    retry_browser_job,
    update_browser_account,
)

router = APIRouter(prefix="/browser", tags=["browser"])

JOB_STATUS_PATTERN = "^(QUEUED|RUNNING|SUCCESS|FAILED|NEEDS_USER_ACTION|UNKNOWN|CANCELLED)$"


@router.get("/accounts", response_model=BrowserAccountListResponse)
async def get_browser_accounts(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 100,
    status: Annotated[
        str | None,
        Query(
            pattern=(
                "^(ACTIVE|NEEDS_LOGIN|NEEDS_REAUTHENTICATION|DISABLED|ERROR)$"
            )
        ),
    ] = None,
) -> BrowserAccountListResponse:
    items, total = await list_browser_accounts(
        db_session, current_user.id, page=page, page_size=page_size, status=status
    )
    return BrowserAccountListResponse(
        items=[BrowserAccountResponse.model_validate(item) for item in items], total=total
    )


@router.post("/accounts", response_model=BrowserAccountResponse, status_code=201)
async def post_browser_account(
    body: BrowserAccountCreate,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> BrowserAccountResponse:
    account = await create_browser_account(
        db_session,
        current_user.id,
        platform=body.platform,
        display_name=body.display_name,
        handle=body.handle,
        profile_image_url=body.profile_image_url,
        metadata=body.metadata,
    )
    await write_audit_log_from_request(
        db_session,
        request,
        action="browser_account_created",
        entity_type="browser_account",
        entity_id=str(account.id),
        details={"platform": account.platform, "display_name": account.display_name},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return BrowserAccountResponse.model_validate(account)


@router.get("/accounts/{account_id}", response_model=BrowserAccountResponse)
async def get_browser_account_detail(
    account_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> BrowserAccountResponse:
    account = await get_browser_account(db_session, current_user.id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Browser account not found")
    return BrowserAccountResponse.model_validate(account)


@router.patch("/accounts/{account_id}", response_model=BrowserAccountResponse)
async def patch_browser_account(
    account_id: UUID,
    body: BrowserAccountUpdate,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> BrowserAccountResponse:
    account = await update_browser_account(
        db_session,
        current_user.id,
        account_id,
        display_name=body.display_name,
        handle=body.handle,
        profile_image_url=body.profile_image_url,
        metadata=body.metadata,
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Browser account not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="browser_account_updated",
        entity_type="browser_account",
        entity_id=str(account.id),
        details={"display_name": account.display_name},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return BrowserAccountResponse.model_validate(account)


@router.post("/accounts/{account_id}/session/clear", response_model=BrowserAccountResponse)
async def post_clear_browser_session(
    account_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> BrowserAccountResponse:
    profile = await clear_browser_session_state(db_session, current_user.id, account_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Browser account not found")
    account = await get_browser_account(db_session, current_user.id, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Browser account not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="browser_session_cleared",
        entity_type="browser_account",
        entity_id=str(account.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return BrowserAccountResponse.model_validate(account)


@router.post("/accounts/{account_id}/login", response_model=BrowserJobResponse, status_code=201)
async def post_browser_login(
    account_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> BrowserJobResponse:
    return await _create_account_job(
        db_session, current_user, request, account_id, job_type="LOGIN"
    )


@router.post(
    "/accounts/{account_id}/check-session",
    response_model=BrowserJobResponse,
    status_code=201,
)
async def post_browser_session_check(
    account_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> BrowserJobResponse:
    return await _create_account_job(
        db_session, current_user, request, account_id, job_type="CHECK_SESSION"
    )


@router.get("/jobs", response_model=BrowserJobListResponse)
async def get_browser_jobs(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 100,
    status: Annotated[str | None, Query(pattern=JOB_STATUS_PATTERN)] = None,
    account_id: UUID | None = None,
) -> BrowserJobListResponse:
    items, total = await list_browser_jobs(
        db_session,
        current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        account_id=account_id,
    )
    return BrowserJobListResponse(
        items=[BrowserJobResponse.model_validate(item) for item in items], total=total
    )


@router.post("/jobs", response_model=BrowserJobResponse, status_code=201)
async def post_browser_job(
    body: BrowserJobCreate,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> BrowserJobResponse:
    try:
        job = await create_browser_job(
            db_session,
            current_user.id,
            account_id=body.account_id,
            job_type=body.job_type,
            content_item_id=body.content_item_id,
            idempotency_key=body.idempotency_key,
            scheduled_for=body.scheduled_for,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="browser_job_created",
        entity_type="browser_job",
        entity_id=str(job.id),
        details={"job_type": job.job_type, "status": job.status},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return BrowserJobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=BrowserJobDetailResponse)
async def get_browser_job_detail(
    job_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> BrowserJobDetailResponse:
    job = await get_browser_job(db_session, current_user.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Browser job not found")
    events = await list_browser_events(db_session, current_user.id, job.id)
    return BrowserJobDetailResponse(
        **BrowserJobResponse.model_validate(job).model_dump(),
        events=[BrowserEventResponse.model_validate(event) for event in events],
    )


@router.post("/jobs/{job_id}/retry", response_model=BrowserJobResponse)
async def post_browser_job_retry(
    job_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> BrowserJobResponse:
    try:
        job = await retry_browser_job(db_session, current_user.id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Browser job not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="browser_job_retried",
        entity_type="browser_job",
        entity_id=str(job.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return BrowserJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=BrowserJobResponse)
async def post_browser_job_cancel(
    job_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> BrowserJobResponse:
    try:
        job = await cancel_browser_job(db_session, current_user.id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Browser job not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="browser_job_cancelled",
        entity_type="browser_job",
        entity_id=str(job.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return BrowserJobResponse.model_validate(job)


@router.get("/workers", response_model=BrowserWorkerListResponse)
async def get_browser_workers(
    current_user: CurrentUser, db_session: DbSession
) -> BrowserWorkerListResponse:
    del current_user
    workers = await list_browser_workers(db_session)
    return BrowserWorkerListResponse(
        items=[BrowserWorkerResponse.model_validate(worker) for worker in workers],
        total=len(workers),
    )


@router.get("/activity", response_model=BrowserActivityListResponse)
async def get_browser_activity(
    current_user: CurrentUser,
    db_session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    account_id: UUID | None = None,
) -> BrowserActivityListResponse:
    events = await list_browser_activity(
        db_session, current_user.id, limit=limit, account_id=account_id
    )
    return BrowserActivityListResponse(
        items=[BrowserEventResponse.model_validate(event) for event in events],
        total=len(events),
    )


async def _create_account_job(
    db_session: DbSession,
    current_user: CurrentUser,
    request: Request,
    account_id: UUID,
    *,
    job_type: str,
) -> BrowserJobResponse:
    try:
        job = await create_browser_job(
            db_session,
            current_user.id,
            account_id=account_id,
            job_type=job_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action=f"browser_{job_type.lower()}_queued",
        entity_type="browser_job",
        entity_id=str(job.id),
        details={"account_id": str(account_id)},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return BrowserJobResponse.model_validate(job)
