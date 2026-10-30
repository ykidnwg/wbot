"""Audit log API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from app.services.audit_log import list_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
async def get_audit_logs(
    _current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    entity_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    actor_id: Annotated[UUID | None, Query()] = None,
) -> AuditLogListResponse:
    """List audit logs with optional filtering and pagination."""
    items, total = await list_audit_logs(
        db_session,
        page=page,
        page_size=page_size,
        entity_type=entity_type,
        action=action,
        actor_id=actor_id,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )
