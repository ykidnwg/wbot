"""Authenticated persona profile and approval routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.dependencies import CurrentUser, DbSession
from app.models.persona import Persona
from app.schemas.persona import (
    PersonaCreate,
    PersonaListResponse,
    PersonaResponse,
    PersonaVersionResponse,
)
from app.schemas.persona_batch import (
    PersonaBatchCreate,
    PersonaBatchDetail,
    PersonaBatchListResponse,
    PersonaBatchSummary,
    PersonaCandidateResponse,
    PersonaSelectedApproval,
    PersonaSelectedApprovalResponse,
)
from app.services.audit_log import write_audit_log_from_request
from app.services.persona import (
    approve_persona,
    create_persona,
    get_persona,
    list_persona_versions,
    list_personas,
    update_draft,
)
from app.services.persona_batch import (
    approve_selected_candidates,
    create_batch,
    get_batch,
    list_batches,
)

router = APIRouter(prefix="/personas", tags=["personas"])


async def _owned_persona(db_session: DbSession, owner_id: UUID, persona_id: UUID) -> Persona:
    persona = await get_persona(db_session, owner_id, persona_id)
    if persona is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")
    return persona


@router.get("", response_model=PersonaListResponse)
async def get_personas(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PersonaListResponse:
    items, total = await list_personas(db_session, current_user.id, page=page, page_size=page_size)
    return PersonaListResponse(
        items=[PersonaResponse.model_validate(persona) for persona in items], total=total
    )


@router.post("", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def post_persona(
    body: PersonaCreate,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> PersonaResponse:
    persona = await create_persona(db_session, current_user.id, body)
    await write_audit_log_from_request(
        db_session,
        request,
        action="persona_created",
        entity_type="persona",
        entity_id=str(persona.id),
        details={"name": persona.name},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return PersonaResponse.model_validate(persona)


@router.post("/batches", response_model=PersonaBatchDetail, status_code=status.HTTP_201_CREATED)
async def post_persona_batch(
    body: PersonaBatchCreate,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> PersonaBatchDetail:
    batch, candidates = await create_batch(db_session, current_user.id, body)
    await write_audit_log_from_request(
        db_session,
        request,
        action="persona_batch_created",
        entity_type="persona_batch",
        entity_id=str(batch.id),
        details={"candidate_count": len(candidates)},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return PersonaBatchDetail(
        id=batch.id,
        name=batch.name,
        status=batch.status,
        candidate_count=len(candidates),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        candidates=[PersonaCandidateResponse.model_validate(candidate) for candidate in candidates],
    )


@router.get("/batches", response_model=PersonaBatchListResponse)
async def get_persona_batches(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PersonaBatchListResponse:
    rows, total = await list_batches(db_session, current_user.id, page=page, page_size=page_size)
    return PersonaBatchListResponse(
        items=[
            PersonaBatchSummary(
                id=batch.id,
                name=batch.name,
                status=batch.status,
                candidate_count=count,
                created_at=batch.created_at,
                updated_at=batch.updated_at,
            )
            for batch, count in rows
        ],
        total=total,
    )


@router.get("/batches/{batch_id}", response_model=PersonaBatchDetail)
async def get_persona_batch_detail(
    batch_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> PersonaBatchDetail:
    result = await get_batch(db_session, current_user.id, batch_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona batch not found")
    batch, candidates = result
    return PersonaBatchDetail(
        id=batch.id,
        name=batch.name,
        status=batch.status,
        candidate_count=len(candidates),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        candidates=[PersonaCandidateResponse.model_validate(item) for item in candidates],
    )


@router.post(
    "/batches/{batch_id}/approve-selected",
    response_model=PersonaSelectedApprovalResponse,
)
async def post_approve_selected_candidates(
    batch_id: UUID,
    body: PersonaSelectedApproval,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> PersonaSelectedApprovalResponse:
    result = await get_batch(db_session, current_user.id, batch_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona batch not found")
    batch, _ = result
    try:
        personas = await approve_selected_candidates(
            db_session, current_user.id, batch, body.candidate_ids
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="persona_batch_candidates_approved",
        entity_type="persona_batch",
        entity_id=str(batch.id),
        details={"approved_count": len(personas)},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return PersonaSelectedApprovalResponse(
        approved_count=len(personas),
        personas=[PersonaResponse.model_validate(persona) for persona in personas],
    )


@router.post("/batches/{batch_id}/candidates/{candidate_id}/regenerate", status_code=503)
async def post_regenerate_candidate(
    batch_id: UUID,
    candidate_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
) -> None:
    """Report that regeneration needs a configured provider without altering any candidate."""
    result = await get_batch(db_session, current_user.id, batch_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona batch not found")
    _, candidates = result
    if not any(candidate.id == candidate_id for candidate in candidates):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Persona candidate not found"
        )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="NEEDS_CREDENTIALS: image/caption candidate provider is not configured",
    )


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona_detail(
    persona_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> PersonaResponse:
    persona = await _owned_persona(db_session, current_user.id, persona_id)
    return PersonaResponse.model_validate(persona)


@router.put("/{persona_id}", response_model=PersonaResponse)
async def put_persona(
    persona_id: UUID,
    body: PersonaCreate,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> PersonaResponse:
    persona = await _owned_persona(db_session, current_user.id, persona_id)
    try:
        await update_draft(db_session, persona, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="persona_draft_updated",
        entity_type="persona",
        entity_id=str(persona.id),
        details={"name": persona.name},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return PersonaResponse.model_validate(persona)


@router.post("/{persona_id}/approve", response_model=PersonaVersionResponse)
async def approve_persona_version(
    persona_id: UUID,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> PersonaVersionResponse:
    persona = await _owned_persona(db_session, current_user.id, persona_id)
    try:
        version = await approve_persona(db_session, persona, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="persona_approved",
        entity_type="persona",
        entity_id=str(persona.id),
        details={"version_no": version.version_no},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return PersonaVersionResponse.model_validate(version)


@router.get("/{persona_id}/versions", response_model=list[PersonaVersionResponse])
async def get_persona_versions(
    persona_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> list[PersonaVersionResponse]:
    await _owned_persona(db_session, current_user.id, persona_id)
    versions = await list_persona_versions(db_session, current_user.id, persona_id)
    return [PersonaVersionResponse.model_validate(version) for version in versions]
