from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    audit_logs,
    auth,
    content,
    dashboard,
    health,
    media,
    notifications,
    personas,
    settings,
    social,
)
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.services.auth import create_initial_admin
from app.services.setting import ensure_default_settings

app_settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with SessionLocal() as db_session:
        await create_initial_admin(db_session)
        await ensure_default_settings(db_session)
        await db_session.commit()
    yield
    await engine.dispose()


app = FastAPI(title=app_settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(audit_logs.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(social.router, prefix="/api/v1")
app.include_router(personas.router, prefix="/api/v1")
