"""Owner-scoped image generation and media asset routes."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.models.content import MediaAsset
from app.models.persona import Persona
from app.providers.image import MockImageProvider
from app.schemas.media import (
    ImageGenerationRequest,
    MediaAssetListResponse,
    MediaAssetResponse,
    ProviderStatusResponse,
)
from app.services.media import ObjectStorage, create_media_asset, get_media_asset

router = APIRouter(prefix="/media", tags=["media"])
storage = ObjectStorage(Path("/tmp/ai-social-media"))


@router.get("/provider", response_model=ProviderStatusResponse)
async def get_image_provider_status(_current_user: CurrentUser) -> ProviderStatusResponse:
    provider = MockImageProvider()
    return ProviderStatusResponse(
        provider=provider.name, model=provider.model, mode="mock", health=provider.get_health()
    )


@router.post("/generate", response_model=MediaAssetResponse, status_code=201)
async def generate_image(
    body: ImageGenerationRequest, current_user: CurrentUser, db_session: DbSession
) -> MediaAssetResponse:
    persona = await db_session.scalar(
        select(Persona).where(
            Persona.id == body.persona_id,
            Persona.owner_id == current_user.id,
            Persona.status == "approved",
        )
    )
    if persona is None:
        raise HTTPException(
            status_code=409, detail="Only an owned, approved persona can generate an image"
        )
    provider = MockImageProvider()
    try:
        asset = await create_media_asset(
            db_session,
            storage,
            current_user.id,
            persona.id,
            body.prompt,
            provider.generate_image(prompt=body.prompt),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db_session.commit()
    return MediaAssetResponse.model_validate(asset)


@router.get("", response_model=MediaAssetListResponse)
async def list_media(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MediaAssetListResponse:
    base = select(MediaAsset).where(MediaAsset.owner_id == current_user.id)
    total = await db_session.scalar(select(func.count()).select_from(base.subquery())) or 0
    result = await db_session.scalars(
        base.order_by(MediaAsset.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return MediaAssetListResponse(
        items=[MediaAssetResponse.model_validate(asset) for asset in result.all()], total=total
    )


@router.get("/{asset_id}/preview")
async def preview_media(
    asset_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> Response:
    asset = await get_media_asset(db_session, current_user.id, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    try:
        data = storage.get(asset.storage_key)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Media storage is unavailable") from exc
    return Response(content=data, media_type=asset.mime_type)


@router.delete("/{asset_id}", status_code=204)
async def delete_media(asset_id: UUID, current_user: CurrentUser, db_session: DbSession) -> None:
    asset = await get_media_asset(db_session, current_user.id, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    try:
        storage.delete(asset.storage_key)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Media storage is unavailable") from exc
    await db_session.delete(asset)
    await db_session.commit()
