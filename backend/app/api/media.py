"""Owner-scoped image generation and media asset routes."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.content import MediaAsset
from app.models.persona import Persona
from app.providers.caption import ProviderError
from app.schemas.media import (
    ImageGenerationRequest,
    MediaAssetListResponse,
    MediaAssetResponse,
    ProviderStatusResponse,
)
from app.services.media import ObjectStorage, create_media_asset, get_media_asset
from app.services.providers import build_image_provider, get_provider_statuses

router = APIRouter(prefix="/media", tags=["media"])
storage = ObjectStorage(Path(get_settings().media_storage_root))


@router.get("/provider", response_model=ProviderStatusResponse)
async def get_image_provider_status(
    _current_user: CurrentUser, db_session: DbSession
) -> ProviderStatusResponse:
    statuses = await get_provider_statuses(db_session)
    image = next(item for item in statuses if item.kind == "image")
    return ProviderStatusResponse(
        provider="openai" if image.mode == "live" else "mock",
        model=image.model,
        mode=image.mode,
        health=image.status,
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
    provider = await build_image_provider(db_session)
    try:
        generated = provider.generate_image(
            prompt=body.prompt, aspect_ratio=body.aspect_ratio
        )
        asset = await create_media_asset(
            db_session,
            storage,
            current_user.id,
            persona.id,
            body.prompt,
            generated,
        )
    except ProviderError as exc:
        if exc.safe_message == "NEEDS_CREDENTIALS" or exc.category == "auth":
            raise HTTPException(status_code=503, detail="NEEDS_CREDENTIALS") from exc
        if exc.category == "rate_limit":
            raise HTTPException(status_code=429, detail=exc.safe_message) from exc
        if exc.category == "validation":
            raise HTTPException(status_code=422, detail=exc.safe_message) from exc
        raise HTTPException(status_code=502, detail=exc.safe_message) from exc
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
