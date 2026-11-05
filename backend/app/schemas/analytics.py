"""First-party analytics response contracts."""

from uuid import UUID

from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    total_content: int
    published_content: int
    approved_content: int
    upcoming_schedules: int
    failed_publishing_jobs: int
    total_clicks: int
    active_campaigns: int
    tracked_links: int


class DailyMetric(BaseModel):
    date: str
    value: int


class CampaignPerformance(BaseModel):
    campaign_id: UUID
    name: str
    status: str
    clicks: int


class LinkPerformance(BaseModel):
    link_id: UUID
    label: str
    tracking_id: str
    campaign_name: str
    clicks: int


class AnalyticsOverviewResponse(BaseModel):
    summary: AnalyticsSummary
    clicks_by_day: list[DailyMetric]
    campaign_performance: list[CampaignPerformance]
    link_performance: list[LinkPerformance]
