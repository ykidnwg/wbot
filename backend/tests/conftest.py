import asyncio
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

test_database_path = Path(tempfile.gettempdir()) / "ai_social_backend_test.db"
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite+aiosqlite:///{test_database_path.as_posix()}",
        "DATABASE_URL_SYNC": f"sqlite:///{test_database_path.as_posix()}",
        "REDIS_URL": "redis://localhost:6379/15",
        "SESSION_COOKIE_SECURE": "false",
        "INITIAL_ADMIN_EMAIL": "",
        "INITIAL_ADMIN_PASSWORD": "",
    }
)

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: F401, E402
    ApprovalEvent,
    AuditLog,
    BrowserAccount,
    BrowserEvent,
    BrowserJob,
    BrowserProfile,
    BrowserWorker,
    Campaign,
    CampaignClick,
    CampaignLink,
    ContentItem,
    ContentVersion,
    GenerationJob,
    MediaAsset,
    Notification,
    OAuthState,
    Persona,
    PersonaAssignment,
    PersonaBatch,
    PersonaCandidate,
    PersonaVersion,
    PublishingAttempt,
    PublishingJob,
    Schedule,
    Session,
    Setting,
    SocialConnection,
    SocialTarget,
    User,
)


def _reset_database() -> None:
    loop = asyncio.new_event_loop()

    async def _do() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    loop.run_until_complete(_do())
    loop.close()


def _dispose_engine() -> None:
    loop = asyncio.new_event_loop()
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture(autouse=True)
def clean_database() -> Iterator[None]:
    _reset_database()
    yield
    _reset_database()
    _dispose_engine()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def run_async(coro: Any) -> Any:
    """Run an async function from sync test code using a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
