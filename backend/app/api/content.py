"""Authenticated content factory routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.content import (
    CaptionGenerationRequest,
    ContentApprovalRequest,
    ContentCaptionUpdateRequest,
    ContentItemResponse,
    ContentListResponse,
    ContentVersionResponse,
)
from app.services.audit_log import write_audit_log_from_request
from app.services.content import (
    decide_content,
    generate_caption_draft,
    list_content,
    list_content_versions,
    update_content_caption,
)

router = APIRouter(prefix="/content", tags=["content"])


@router.get("", response_model=ContentListResponse)
async def get_content(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ContentListResponse:
    items, total = await list_content(db_session, current_user.id, page=page, page_size=page_size)
    return ContentListResponse(
        items=[ContentItemResponse.model_validate(item) for item in items], total=total
    )


@router.post("/generate-caption", response_model=ContentItemResponse, status_code=201)
async def post_generate_caption(
    body: CaptionGenerationRequest,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> ContentItemResponse:
    try:
        item = await generate_caption_draft(db_session, current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="content_caption_generated",
        entity_type="content_item",
        entity_id=str(item.id),
        details={"provider": item.provider, "status": item.status},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return ContentItemResponse.model_validate(item)


@router.put("/{content_id}/caption", response_model=ContentItemResponse)
async def put_content_caption(
    content_id: UUID,
    body: ContentCaptionUpdateRequest,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> ContentItemResponse:
    try:
        item = await update_content_caption(db_session, current_user.id, content_id, body.caption)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Content item not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="content_caption_version_created",
        entity_type="content_item",
        entity_id=str(item.id),
        details={"version_no": item.version_no, "approval_required": True},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return ContentItemResponse.model_validate(item)


@router.get("/{content_id}/versions", response_model=list[ContentVersionResponse])
async def get_content_versions(
    content_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> list[ContentVersionResponse]:
    versions = await list_content_versions(db_session, current_user.id, content_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Content item not found")
    return [ContentVersionResponse.model_validate(version) for version in versions]


@router.post("/{content_id}/approval", response_model=ContentItemResponse)
async def post_content_approval(
    content_id: UUID,
    body: ContentApprovalRequest,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> ContentItemResponse:
    try:
        item = await decide_content(
            db_session, current_user.id, content_id, body.decision, body.reason
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Content item not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action=f"content_{body.decision}",
        entity_type="content_item",
        entity_id=str(item.id),
        details={"version_no": item.version_no},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return ContentItemResponse.model_validate(item)
