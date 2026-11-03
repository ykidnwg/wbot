"""Authenticated Meta social account, target, and persona assignment routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select, update

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.social import PersonaAssignment, SocialTarget
from app.providers.meta import MetaGraphAdapter
from app.schemas.social import (
    OAuthStartResponse,
    PersonaAssignmentRequest,
    PersonaAssignmentResponse,
    ProviderStatusResponse,
    SocialConnectionResponse,
    SocialListResponse,
    SocialTargetResponse,
    TargetListResponse,
)
from app.services.audit_log import write_audit_log_from_request
from app.services.social import (
    META_PERMISSIONS,
    assign_persona,
    consume_oauth_state,
    create_oauth_state,
    list_connections,
    list_targets,
    meta_config,
    remove_assignment,
    sync_pages,
)

router = APIRouter(prefix="/social", tags=["social"])
settings = get_settings()


@router.get("/provider-status", response_model=ProviderStatusResponse)
async def get_provider_status(_current_user: CurrentUser) -> ProviderStatusResponse:
    config = meta_config(settings)
    return ProviderStatusResponse(
        provider="facebook",
        status="configured" if config else "NEEDS_CREDENTIALS",
        graph_api_version=settings.meta_graph_api_version,
        required_permissions=META_PERMISSIONS,
    )


@router.get("/connections", response_model=SocialListResponse)
async def get_connections(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SocialListResponse:
    rows, total = await list_connections(db_session, current_user.id, page, page_size)
    return SocialListResponse(
        items=[SocialConnectionResponse.model_validate(row) for row in rows], total=total
    )


@router.get("/targets", response_model=TargetListResponse)
async def get_targets(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TargetListResponse:
    rows, total = await list_targets(db_session, current_user.id, page, page_size)
    items: list[SocialTargetResponse] = []
    for row in rows:
        assignment = await db_session.scalar(
            select(PersonaAssignment.persona_id).where(
                PersonaAssignment.owner_id == current_user.id,
                PersonaAssignment.social_target_id == row.id,
                PersonaAssignment.active.is_(True),
            )
        )
        item = SocialTargetResponse.model_validate(row)
        item.assigned_persona_id = assignment
        items.append(item)
    return TargetListResponse(items=items, total=total)


@router.get("/assignments", response_model=list[PersonaAssignmentResponse])
async def get_assignments(
    current_user: CurrentUser, db_session: DbSession
) -> list[PersonaAssignmentResponse]:
    rows = await db_session.scalars(
        select(PersonaAssignment).where(
            PersonaAssignment.owner_id == current_user.id,
            PersonaAssignment.active.is_(True),
        )
    )
    return [PersonaAssignmentResponse.model_validate(row) for row in rows.all()]


@router.get("/oauth/facebook/start", response_model=OAuthStartResponse)
async def start_facebook_oauth(
    current_user: CurrentUser, db_session: DbSession
) -> OAuthStartResponse:
    config = meta_config(settings)
    if config is None:
        raise HTTPException(status_code=503, detail="NEEDS_CREDENTIALS")
    raw_state, expires_at = await create_oauth_state(
        db_session, current_user.id, config.redirect_uri
    )
    await db_session.commit()
    return OAuthStartResponse(
        authorization_url=MetaGraphAdapter(config).authorization_url(raw_state),
        expires_at=expires_at,
    )


@router.get("/oauth/facebook/callback")
async def facebook_oauth_callback(
    state: str,
    code: str,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> SocialConnectionResponse:
    config = meta_config(settings)
    if config is None:
        raise HTTPException(status_code=503, detail="NEEDS_CREDENTIALS")
    consumed = await consume_oauth_state(db_session, current_user.id, state, config.redirect_uri)
    if consumed is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    try:
        connection = await sync_pages(
            db_session,
            current_user.id,
            settings,
            MetaGraphAdapter(config),
            code,
            config.redirect_uri,
        )
    except ValueError as exc:
        await db_session.rollback()
        raise HTTPException(status_code=502, detail="Facebook authorization failed") from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="facebook_connection_created",
        entity_type="social_connection",
        entity_id=str(connection.id),
        details={"platform": "facebook", "target_sync": True},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return SocialConnectionResponse.model_validate(connection)


@router.post("/targets/{target_id}/assignment", response_model=PersonaAssignmentResponse)
async def put_assignment(
    target_id: UUID,
    body: PersonaAssignmentRequest,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> PersonaAssignmentResponse:
    try:
        assignment = await assign_persona(db_session, current_user.id, target_id, body.persona_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="persona_assigned_to_social_target",
        entity_type="persona_assignment",
        entity_id=str(assignment.id),
        details={"target_id": str(target_id), "persona_id": str(body.persona_id)},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return PersonaAssignmentResponse.model_validate(assignment)


@router.delete("/targets/{target_id}/assignment", status_code=204)
async def delete_assignment(
    target_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> None:
    assignment = await remove_assignment(db_session, current_user.id, target_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Persona assignment not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="persona_assignment_removed",
        entity_type="persona_assignment",
        entity_id=str(assignment.id),
        details={"target_id": str(target_id)},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()


@router.delete("/connections/{connection_id}", status_code=204)
async def disconnect(
    connection_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> None:
    from app.models.social import SocialConnection

    connection = await db_session.scalar(
        select(SocialConnection).where(
            SocialConnection.id == connection_id, SocialConnection.owner_id == current_user.id
        )
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="Social connection not found")
    connection.status = "revoked"
    await db_session.execute(
        update(SocialTarget)
        .where(
            SocialTarget.owner_id == current_user.id,
            SocialTarget.connection_id == connection.id,
        )
        .values(status="needs_reconnect")
    )
    await write_audit_log_from_request(
        db_session,
        request,
        action="social_connection_disconnected",
        entity_type="social_connection",
        entity_id=str(connection.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
