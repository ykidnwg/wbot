from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.dependencies import CurrentUser, DbSession
from app.models.content import ContentItem, MediaAsset
from app.models.persona import Persona
from app.models.social import SocialConnection
from app.schemas.dashboard import DashboardServices, DashboardSummaryResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: CurrentUser, db_session: DbSession
) -> DashboardSummaryResponse:
    owner = current_user.id
    connected_accounts = await db_session.scalar(
        select(func.count()).select_from(SocialConnection).where(
            SocialConnection.owner_id == owner, SocialConnection.status == "connected"
        )
    ) or 0
    active_personas = await db_session.scalar(
        select(func.count()).select_from(Persona).where(
            Persona.owner_id == owner, Persona.status == "approved"
        )
    ) or 0
    generated_images = await db_session.scalar(
        select(func.count()).select_from(MediaAsset).where(MediaAsset.owner_id == owner)
    ) or 0
    pending_approval = await db_session.scalar(
        select(func.count()).select_from(ContentItem).where(
            ContentItem.owner_id == owner, ContentItem.status == "draft"
        )
    ) or 0
    return DashboardSummaryResponse(
        connected_accounts=connected_accounts,
        active_personas=active_personas,
        generated_images=generated_images,
        pending_approval=pending_approval,
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
