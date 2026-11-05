"""Owner-scoped schedule routes."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.schedule import ScheduleCreateRequest, ScheduleListResponse, ScheduleResponse
from app.services.audit_log import write_audit_log_from_request
from app.services.schedule import cancel_schedule, create_schedule, list_schedules

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=ScheduleListResponse)
async def get_schedules(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 100,
    status: Annotated[
        str | None,
        Query(pattern="^(scheduled|cancelled|publishing|published|failed|uncertain)$"),
    ] = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> ScheduleListResponse:
    items, total = await list_schedules(
        db_session,
        current_user.id,
        page=page,
        page_size=page_size,
        status=status,
        start=start,
        end=end,
    )
    return ScheduleListResponse(
        items=[ScheduleResponse.model_validate(item) for item in items], total=total
    )


@router.post("", response_model=ScheduleResponse, status_code=201)
async def post_schedule(
    body: ScheduleCreateRequest,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> ScheduleResponse:
    try:
        schedule = await create_schedule(db_session, current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="schedule_created",
        entity_type="schedule",
        entity_id=str(schedule.id),
        details={
            "content_item_id": str(schedule.content_item_id),
            "social_target_id": str(schedule.social_target_id)
            if schedule.social_target_id
            else None,
            "browser_account_id": str(schedule.browser_account_id)
            if schedule.browser_account_id
            else None,
            "scheduled_for": schedule.scheduled_for.isoformat(),
        },
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return ScheduleResponse.model_validate(schedule)


@router.delete("/{schedule_id}", response_model=ScheduleResponse)
async def delete_schedule(
    schedule_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> ScheduleResponse:
    try:
        schedule = await cancel_schedule(db_session, current_user.id, schedule_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="schedule_cancelled",
        entity_type="schedule",
        entity_id=str(schedule.id),
        details={"status": schedule.status},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return ScheduleResponse.model_validate(schedule)
