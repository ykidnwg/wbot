"""Owner-scoped campaigns, tracked links, and first-party click recording."""

import secrets
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignClick, CampaignLink
from app.models.persona import Persona
from app.schemas.campaign import CampaignCreateRequest, CampaignLinkCreateRequest


async def list_campaigns(
    db: AsyncSession,
    owner_id: UUID,
    *,
    page: int,
    page_size: int,
    status: str | None = None,
) -> tuple[list[Campaign], int]:
    conditions = [Campaign.owner_id == owner_id]
    if status:
        conditions.append(Campaign.status == status)
    base = select(Campaign).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await db.scalars(
        base.order_by(Campaign.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.all()), total


async def create_campaign(
    db: AsyncSession, owner_id: UUID, payload: CampaignCreateRequest
) -> Campaign:
    if payload.persona_id is not None:
        persona = await db.scalar(
            select(Persona).where(
                Persona.id == payload.persona_id,
                Persona.owner_id == owner_id,
                Persona.status == "approved",
            )
        )
        if persona is None:
            raise ValueError("Campaign persona must be owned and approved")
    if payload.destination_url:
        _validate_url(payload.destination_url)
    if payload.starts_at and payload.ends_at and payload.ends_at <= payload.starts_at:
        raise ValueError("Campaign end time must be after the start time")
    campaign = Campaign(
        owner_id=owner_id,
        persona_id=payload.persona_id,
        name=payload.name.strip(),
        description=payload.description,
        platform=payload.platform,
        destination_url=payload.destination_url,
        status="draft",
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def update_campaign_status(
    db: AsyncSession, owner_id: UUID, campaign_id: UUID, status: str
) -> Campaign | None:
    campaign = await db.scalar(
        select(Campaign)
        .where(Campaign.id == campaign_id, Campaign.owner_id == owner_id)
        .with_for_update()
    )
    if campaign is None:
        return None
    campaign.status = status
    await db.flush()
    await db.refresh(campaign)
    return campaign


async def get_campaign(
    db: AsyncSession, owner_id: UUID, campaign_id: UUID
) -> Campaign | None:
    return await db.scalar(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.owner_id == owner_id)
    )


async def list_campaign_links(
    db: AsyncSession, owner_id: UUID, campaign_id: UUID
) -> list[CampaignLink]:
    rows = await db.scalars(
        select(CampaignLink)
        .where(
            CampaignLink.owner_id == owner_id,
            CampaignLink.campaign_id == campaign_id,
        )
        .order_by(CampaignLink.created_at.desc())
    )
    return list(rows.all())


async def create_campaign_link(
    db: AsyncSession, owner_id: UUID, campaign_id: UUID, payload: CampaignLinkCreateRequest
) -> CampaignLink:
    campaign = await get_campaign(db, owner_id, campaign_id)
    if campaign is None:
        raise ValueError("Campaign not found")
    _validate_url(payload.affiliate_url)
    tracking_id = await _unique_tracking_id(db)
    link = CampaignLink(
        owner_id=owner_id,
        campaign_id=campaign.id,
        label=payload.label.strip(),
        affiliate_url=payload.affiliate_url,
        tracking_id=tracking_id,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        utm_term=payload.utm_term,
        utm_content=payload.utm_content,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link


async def record_click(
    db: AsyncSession, tracking_id: str, *, referrer: str | None = None
) -> str | None:
    link = await db.scalar(
        select(CampaignLink).where(CampaignLink.tracking_id == tracking_id)
    )
    if link is None:
        return None
    referrer_host = None
    if referrer:
        try:
            referrer_host = urlparse(referrer).hostname
        except ValueError:
            referrer_host = None
    db.add(
        CampaignClick(
            owner_id=link.owner_id,
            campaign_link_id=link.id,
            clicked_at=datetime.now(UTC),
            referrer_host=(referrer_host or "")[:255] or None,
        )
    )
    await db.flush()
    return build_destination_url(link)


def build_destination_url(link: CampaignLink) -> str:
    parsed = urlparse(link.affiliate_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    utm = {
        "utm_source": link.utm_source,
        "utm_medium": link.utm_medium,
        "utm_campaign": link.utm_campaign or link.tracking_id,
        "utm_term": link.utm_term,
        "utm_content": link.utm_content,
    }
    for key, value in utm.items():
        if value:
            query.setdefault(key, value)
    query["wbot_tracking_id"] = link.tracking_id
    return urlunparse(parsed._replace(query=urlencode(query)))


def _validate_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError("URL must be a valid HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("URL must not contain embedded credentials")


async def _unique_tracking_id(db: AsyncSession) -> str:
    for _ in range(5):
        candidate = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
        exists = await db.scalar(
            select(CampaignLink.id).where(CampaignLink.tracking_id == candidate)
        )
        if exists is None:
            return candidate
    raise ValueError("Could not allocate a unique tracking identifier")
