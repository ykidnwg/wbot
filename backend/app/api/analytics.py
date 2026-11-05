"""First-party analytics routes."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.analytics import AnalyticsOverviewResponse
from app.services.analytics import (
    get_campaign_performance,
    get_click_series,
    get_link_performance,
    get_summary,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOverviewResponse)
async def get_analytics(
    current_user: CurrentUser,
    db_session: DbSession,
    days: Annotated[int, Query(ge=7, le=90)] = 30,
) -> AnalyticsOverviewResponse:
    return AnalyticsOverviewResponse(
        summary=await get_summary(db_session, current_user.id),
        clicks_by_day=await get_click_series(db_session, current_user.id, days=days),
        campaign_performance=await get_campaign_performance(db_session, current_user.id),
        link_performance=await get_link_performance(db_session, current_user.id),
    )
