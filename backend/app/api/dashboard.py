from fastapi import APIRouter

from app.api.dependencies import CurrentUser
from app.schemas.dashboard import DashboardServices, DashboardSummaryResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(_current_user: CurrentUser) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        connected_accounts=0,
        active_personas=0,
        generated_images=0,
        pending_approval=0,
        scheduled_posts=0,
        published_posts=0,
        failed_posts=0,
        estimated_ai_cost=None,
        services=DashboardServices(
            database="ok",
            worker="not_configured",
            queue="not_configured",
            providers="not_configured",
        ),
    )
