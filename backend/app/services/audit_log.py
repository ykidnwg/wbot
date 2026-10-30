"""Service layer for audit logging."""

import json
from uuid import UUID

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def write_audit_log(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict[str, object] | None = None,
    actor_id: UUID | None = None,
    actor_email: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Create an immutable audit log entry."""
    log_entry = AuditLog(
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
        ip_address=ip_address,
    )
    db.add(log_entry)
    await db.flush()
    return log_entry


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, handling proxy headers safely."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def write_audit_log_from_request(
    db: AsyncSession,
    request: Request,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict[str, object] | None = None,
    actor_id: UUID | None = None,
    actor_email: str | None = None,
) -> AuditLog:
    """Create an audit log entry with IP extracted from the request."""
    return await write_audit_log(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        actor_id=actor_id,
        actor_email=actor_email,
        ip_address=_get_client_ip(request),
    )


async def list_audit_logs(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    entity_type: str | None = None,
    action: str | None = None,
    actor_id: UUID | None = None,
) -> tuple[list[AuditLog], int]:
    """List audit logs with optional filters and pagination."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
        count_query = count_query.where(AuditLog.actor_id == actor_id)

    total = await db.scalar(count_query) or 0
    offset = (page - 1) * page_size
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
    result = await db.scalars(query)
    return list(result.all()), total
