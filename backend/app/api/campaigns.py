"""Owner-scoped campaign and tracked-link routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.dependencies import CurrentUser, DbSession
from app.models.campaign import CampaignLink
from app.schemas.campaign import (
    CampaignCreateRequest,
    CampaignLinkCreateRequest,
    CampaignLinkResponse,
    CampaignListResponse,
    CampaignResponse,
    CampaignStatusRequest,
)
from app.services.audit_log import write_audit_log_from_request
from app.services.campaign import (
    build_destination_url,
    create_campaign,
    create_campaign_link,
    get_campaign,
    list_campaign_links,
    list_campaigns,
    update_campaign_status,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _link_response(link: CampaignLink) -> CampaignLinkResponse:
    return CampaignLinkResponse(
        id=link.id,
        campaign_id=link.campaign_id,
        label=link.label,
        affiliate_url=link.affiliate_url,
        tracking_id=link.tracking_id,
        tracking_path=f"/r/{link.tracking_id}",
        destination_url=build_destination_url(link),
        utm_source=link.utm_source,
        utm_medium=link.utm_medium,
        utm_campaign=link.utm_campaign,
        utm_term=link.utm_term,
        utm_content=link.utm_content,
        created_at=link.created_at,
    )


@router.get("", response_model=CampaignListResponse)
async def get_campaigns(
    current_user: CurrentUser,
    db_session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    status: Annotated[str | None, Query(pattern="^(draft|active|paused|ended|archived)$")] = None,
) -> CampaignListResponse:
    items, total = await list_campaigns(
        db_session, current_user.id, page=page, page_size=page_size, status=status
    )
    return CampaignListResponse(
        items=[CampaignResponse.model_validate(item) for item in items], total=total
    )


@router.post("", response_model=CampaignResponse, status_code=201)
async def post_campaign(
    body: CampaignCreateRequest,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> CampaignResponse:
    try:
        campaign = await create_campaign(db_session, current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="campaign_created",
        entity_type="campaign",
        entity_id=str(campaign.id),
        details={"status": campaign.status},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign_detail(
    campaign_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> CampaignResponse:
    campaign = await get_campaign(db_session, current_user.id, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.patch("/{campaign_id}/status", response_model=CampaignResponse)
async def patch_campaign_status(
    campaign_id: UUID,
    body: CampaignStatusRequest,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> CampaignResponse:
    campaign = await update_campaign_status(
        db_session, current_user.id, campaign_id, body.status
    )
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await write_audit_log_from_request(
        db_session,
        request,
        action="campaign_status_changed",
        entity_type="campaign",
        entity_id=str(campaign.id),
        details={"status": campaign.status},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return CampaignResponse.model_validate(campaign)


@router.get("/{campaign_id}/links", response_model=list[CampaignLinkResponse])
async def get_campaign_links(
    campaign_id: UUID, current_user: CurrentUser, db_session: DbSession
) -> list[CampaignLinkResponse]:
    campaign = await get_campaign(db_session, current_user.id, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    links = await list_campaign_links(db_session, current_user.id, campaign_id)
    return [_link_response(link) for link in links]


@router.post("/{campaign_id}/links", response_model=CampaignLinkResponse, status_code=201)
async def post_campaign_link(
    campaign_id: UUID,
    body: CampaignLinkCreateRequest,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> CampaignLinkResponse:
    campaign = await get_campaign(db_session, current_user.id, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    try:
        link = await create_campaign_link(db_session, current_user.id, campaign_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await write_audit_log_from_request(
        db_session,
        request,
        action="campaign_link_created",
        entity_type="campaign_link",
        entity_id=str(link.id),
        details={"campaign_id": str(link.campaign_id), "tracking_id": link.tracking_id},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    await db_session.refresh(link)
    return _link_response(link)
