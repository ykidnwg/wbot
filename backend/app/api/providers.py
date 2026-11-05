"""Authenticated provider health and configuration status."""

from fastapi import APIRouter

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.provider import ProviderStatusListResponse, ProviderStatusResponse
from app.services.providers import get_provider_statuses

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("", response_model=ProviderStatusListResponse)
async def get_providers(
    _current_user: CurrentUser, db_session: DbSession
) -> ProviderStatusListResponse:
    statuses = await get_provider_statuses(db_session)
    return ProviderStatusListResponse(
        items=[
            ProviderStatusResponse(
                id=item.id,
                label=item.label,
                kind=item.kind,
                mode=item.mode,
                status=item.status,
                model=item.model,
                api_base=item.api_base,
                message=item.message,
            )
            for item in statuses
        ]
    )
