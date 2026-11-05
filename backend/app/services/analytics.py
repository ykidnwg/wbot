"""Analytics derived exclusively from owned first-party records."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignClick, CampaignLink
from app.models.content import ContentItem
from app.models.publishing import PublishingJob, Schedule
from app.schemas.analytics import (
    AnalyticsSummary,
    CampaignPerformance,
    DailyMetric,
    LinkPerformance,
)


async def get_summary(db: AsyncSession, owner_id: UUID) -> AnalyticsSummary:
    total_content = await _count(db, select(ContentItem.id).where(ContentItem.owner_id == owner_id))
    published_content = await _count(
        db,
        select(ContentItem.id).where(
            ContentItem.owner_id == owner_id, ContentItem.status == "published"
        ),
    )
    approved_content = await _count(
        db,
        select(ContentItem.id).where(
            ContentItem.owner_id == owner_id, ContentItem.status == "approved"
        ),
    )
    upcoming = await _count(
        db,
        select(Schedule.id).where(
            Schedule.owner_id == owner_id,
            Schedule.status == "scheduled",
            Schedule.scheduled_for >= datetime.now(UTC),
        ),
    )
    failed_jobs = await _count(
        db,
        select(PublishingJob.id).where(
            PublishingJob.owner_id == owner_id,
            PublishingJob.status.in_(("failed", "uncertain", "needs_credentials")),
        ),
    )
    total_clicks = await _count(
        db, select(CampaignClick.id).where(CampaignClick.owner_id == owner_id)
    )
    active_campaigns = await _count(
        db,
        select(Campaign.id).where(
            Campaign.owner_id == owner_id, Campaign.status == "active"
        ),
    )
    tracked_links = await _count(
        db, select(CampaignLink.id).where(CampaignLink.owner_id == owner_id)
    )
    return AnalyticsSummary(
        total_content=total_content,
        published_content=published_content,
        approved_content=approved_content,
        upcoming_schedules=upcoming,
        failed_publishing_jobs=failed_jobs,
        total_clicks=total_clicks,
        active_campaigns=active_campaigns,
        tracked_links=tracked_links,
    )


async def get_click_series(
    db: AsyncSession, owner_id: UUID, *, days: int = 30
) -> list[DailyMetric]:
    start = (datetime.now(UTC) - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day = func.date(CampaignClick.clicked_at)
    rows = (
        await db.execute(
            select(day, func.count(CampaignClick.id))
            .where(CampaignClick.owner_id == owner_id, CampaignClick.clicked_at >= start)
            .group_by(day)
            .order_by(day)
        )
    ).all()
    counts = {str(row[0]): int(row[1]) for row in rows}
    result: list[DailyMetric] = []
    for offset in range(days):
        current = start + timedelta(days=offset)
        key = current.date().isoformat()
        result.append(DailyMetric(date=key, value=counts.get(key, 0)))
    return result


async def get_campaign_performance(
    db: AsyncSession, owner_id: UUID
) -> list[CampaignPerformance]:
    rows = (
        await db.execute(
            select(
                Campaign.id,
                Campaign.name,
                Campaign.status,
                func.count(CampaignClick.id),
            )
            .outerjoin(CampaignLink, CampaignLink.campaign_id == Campaign.id)
            .outerjoin(CampaignClick, CampaignClick.campaign_link_id == CampaignLink.id)
            .where(Campaign.owner_id == owner_id)
            .group_by(Campaign.id, Campaign.name, Campaign.status)
            .order_by(func.count(CampaignClick.id).desc(), Campaign.name.asc())
            .limit(50)
        )
    ).all()
    return [
        CampaignPerformance(
            campaign_id=row[0],
            name=row[1],
            status=row[2],
            clicks=int(row[3]),
        )
        for row in rows
    ]


async def get_link_performance(
    db: AsyncSession, owner_id: UUID
) -> list[LinkPerformance]:
    rows = (
        await db.execute(
            select(
                CampaignLink.id,
                CampaignLink.label,
                CampaignLink.tracking_id,
                Campaign.name,
                func.count(CampaignClick.id),
            )
            .join(Campaign, Campaign.id == CampaignLink.campaign_id)
            .outerjoin(CampaignClick, CampaignClick.campaign_link_id == CampaignLink.id)
            .where(CampaignLink.owner_id == owner_id)
            .group_by(
                CampaignLink.id,
                CampaignLink.label,
                CampaignLink.tracking_id,
                Campaign.name,
            )
            .order_by(func.count(CampaignClick.id).desc(), CampaignLink.label.asc())
            .limit(100)
        )
    ).all()
    return [
        LinkPerformance(
            link_id=row[0],
            label=row[1],
            tracking_id=row[2],
            campaign_name=row[3],
            clicks=int(row[4]),
        )
        for row in rows
    ]


async def _count(db: AsyncSession, query: Any) -> int:
    return int((await db.scalar(select(func.count()).select_from(query.subquery()))) or 0)
