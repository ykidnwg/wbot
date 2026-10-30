from typing import Literal

from pydantic import BaseModel

ServiceState = Literal["ok", "not_configured"]


class DashboardServices(BaseModel):
    database: Literal["ok"]
    worker: ServiceState
    queue: ServiceState
    providers: ServiceState


class DashboardSummaryResponse(BaseModel):
    connected_accounts: int
    active_personas: int
    generated_images: int
    pending_approval: int
    scheduled_posts: int
    published_posts: int
    failed_posts: int
    estimated_ai_cost: None
    services: DashboardServices
