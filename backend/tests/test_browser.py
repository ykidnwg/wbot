"""Browser accounts, encrypted profiles, durable jobs, and scheduler integration."""

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.browser import BrowserAccount, BrowserJob, BrowserEvent, BrowserProfile
from app.models.content import ContentItem
from app.models.publishing import PublishingJob, Schedule
from app.models.social import SocialConnection  # noqa: F401
from app.models.user import User
from app.services.browser import save_browser_session_state
from app.services.publishing import dispatch_due_schedules
from app.services.social_security import decrypt_token, encrypt_token
from tests.conftest import run_async
from tests.test_personas import _login, _payload

TEST_KEY = base64.urlsafe_b64encode(b"b" * 32).decode()
SESSION_STATE = {
    "cookies": [
        {
            "name": "session",
            "value": "secret-cookie-value",
            "domain": ".facebook.com",
            "path": "/",
            "expires": 2000000000,
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }
    ],
    "origins": [],
}


def _create_account(client: TestClient, display_name: str = "Ops Page") -> dict[str, object]:
    response = client.post(
        "/api/v1/browser/accounts",
        json={
            "platform": "facebook",
            "display_name": display_name,
            "handle": display_name.lower().replace(" ", "-"),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approved_content(client: TestClient, topic: str = "Browser-native publishing") -> str:
    persona = client.post("/api/v1/personas", json=_payload()).json()
    assert client.post(f"/api/v1/personas/{persona['id']}/approve").status_code == 200
    content = client.post(
        "/api/v1/content/generate-caption",
        json={"persona_id": persona["id"], "topic": topic, "platform": "facebook"},
    )
    assert content.status_code == 201, content.text
    content_id = content.json()["id"]
    assert (
        client.post(
            f"/api/v1/content/{content_id}/approval", json={"decision": "approved"}
        ).status_code
        == 200
    )
    return content_id


def _activate_account(account_id: str, storage_state: dict[str, object]) -> None:
    async def _do() -> None:
        async with SessionLocal() as db:
            account = await db.get(BrowserAccount, UUID(account_id))
            assert account is not None
            profile = await db.scalar(
                select(BrowserProfile).where(BrowserProfile.account_id == account.id)
            )
            assert profile is not None
            profile.encrypted_storage_state = encrypt_token(json.dumps(storage_state), TEST_KEY)
            profile.state_updated_at = datetime.now(UTC)
            account.status = "ACTIVE"
            account.session_status = "HEALTHY"
            account.last_checked_at = datetime.now(UTC)
            await db.commit()

    run_async(_do())


def test_browser_account_is_owner_scoped_and_hides_session_state(client: TestClient) -> None:
    _login(client)
    account = _create_account(client)
    assert account["status"] == "NEEDS_LOGIN"
    assert account["session_status"] == "UNKNOWN"
    assert "encrypted_storage_state" not in account
    assert "session_state" not in account

    _login(client, "browser-other@example.com", "other-secret")
    listed = client.get("/api/v1/browser/accounts")
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
    assert client.get(f"/api/v1/browser/accounts/{account['id']}").status_code == 404


def test_session_state_is_encrypted_and_never_returned(client: TestClient) -> None:
    _login(client)
    account = _create_account(client)

    async def _do() -> None:
        async with SessionLocal() as db:
            owner = await db.scalar(select(User).where(User.email == "persona@example.com"))
            assert owner is not None
            await save_browser_session_state(
                db,
                owner.id,
                UUID(account["id"]),
                SESSION_STATE,
                encoded_key=TEST_KEY,
            )
            await db.commit()
            profile = await db.scalar(select(BrowserProfile))
            saved = await db.get(BrowserAccount, UUID(account["id"]))
            assert profile is not None
            assert profile.encrypted_storage_state is not None
            assert "secret-cookie-value" not in profile.encrypted_storage_state
            assert json.loads(
                decrypt_token(profile.encrypted_storage_state, TEST_KEY)
            ) == SESSION_STATE
            assert saved is not None
            assert saved.status == "ACTIVE"
            assert saved.session_status == "HEALTHY"
            event = await db.scalar(
                select(BrowserEvent).where(BrowserEvent.event_type == "SESSION_UPDATED")
            )
            assert event is not None

    run_async(_do())
    refreshed = client.get(f"/api/v1/browser/accounts/{account['id']}")
    assert refreshed.status_code == 200
    assert "encrypted_storage_state" not in refreshed.json()
    assert "secret-cookie-value" not in refreshed.text


def test_browser_job_is_idempotent_and_lists_safe_events(client: TestClient) -> None:
    _login(client)
    content_id = _approved_content(client)
    account = _create_account(client)
    _activate_account(account["id"], SESSION_STATE)

    payload = {
        "account_id": account["id"],
        "content_item_id": content_id,
        "job_type": "PUBLISH",
        "idempotency_key": "browser-test-job-1",
    }
    first = client.post("/api/v1/browser/jobs", json=payload)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/browser/jobs", json=payload)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert first.json()["status"] == "QUEUED"

    jobs = client.get("/api/v1/browser/jobs")
    assert jobs.status_code == 200
    assert jobs.json()["total"] == 1
    detail = client.get(f"/api/v1/browser/jobs/{first.json()['id']}")
    assert detail.status_code == 200
    assert [event["event_type"] for event in detail.json()["events"]] == ["JOB_QUEUED"]
    assert "secret-cookie-value" not in detail.text

    _login(client, "browser-other@example.com", "other-secret")
    assert client.get("/api/v1/browser/jobs").json()["total"] == 0
    assert client.get(f"/api/v1/browser/jobs/{first.json()['id']}").status_code == 404


def test_browser_schedule_dispatches_without_graph_worker(client: TestClient) -> None:
    _login(client)
    content_id = _approved_content(client)
    account = _create_account(client)
    _activate_account(account["id"], SESSION_STATE)
    response = client.post(
        "/api/v1/schedules",
        json={
            "content_item_id": content_id,
            "browser_account_id": account["id"],
            "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert response.status_code == 201, response.text
    schedule = response.json()
    assert schedule["social_target_id"] is None
    assert schedule["browser_account_id"] == account["id"]

    async def _run() -> None:
        from app.services.browser import dispatch_due_browser_schedules

        async with SessionLocal() as db:
            stored = await db.get(Schedule, UUID(schedule["id"]))
            assert stored is not None
            stored.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
            await db.commit()
            assert await dispatch_due_schedules(db) == 0
            assert await dispatch_due_browser_schedules(db) == 1
            await db.commit()
            job = await db.scalar(select(BrowserJob))
            assert job is not None
            assert job.status == "QUEUED"
            assert job.idempotency_key == f"browser-schedule:{schedule['id']}"
            assert job.account_id is not None
            refreshed = await db.get(Schedule, UUID(schedule["id"]))
            assert refreshed is not None and refreshed.status == "publishing"
            content = await db.get(ContentItem, UUID(content_id))
            assert content is not None and content.status == "publishing"
            assert await dispatch_due_browser_schedules(db) == 0
            assert await db.scalar(select(PublishingJob)) is None

    run_async(_run())


def test_stale_browser_job_becomes_unknown_without_retry(client: TestClient) -> None:
    _login(client)
    content_id = _approved_content(client)
    account = _create_account(client)
    _activate_account(account["id"], SESSION_STATE)

    async def _run() -> None:
        from app.services.browser import recover_stale_browser_jobs

        async with SessionLocal() as db:
            owner = await db.scalar(select(User).where(User.email == "persona@example.com"))
            content = await db.get(ContentItem, UUID(content_id))
            assert owner is not None and content is not None
            content.status = "publishing"
            schedule = Schedule(
                owner_id=owner.id,
                content_item_id=content.id,
                browser_account_id=UUID(account["id"]),
                scheduled_for=datetime.now(UTC) - timedelta(minutes=30),
                timezone="UTC",
                status="publishing",
                idempotency_key=f"browser-stale-{uuid4()}",
            )
            db.add(schedule)
            await db.flush()
            job = BrowserJob(
                owner_id=owner.id,
                account_id=UUID(account["id"]),
                schedule_id=schedule.id,
                content_item_id=content.id,
                job_type="PUBLISH",
                status="RUNNING",
                attempts=1,
                idempotency_key=f"browser-stale-job-{uuid4()}",
                started_at=datetime.now(UTC) - timedelta(minutes=30),
                locked_at=datetime.now(UTC) - timedelta(minutes=30),
            )
            db.add(job)
            await db.commit()

            assert await recover_stale_browser_jobs(db, now=datetime.now(UTC)) == 1
            await db.commit()
            await db.refresh(job)
            await db.refresh(schedule)
            await db.refresh(content)
            assert job.status == "UNKNOWN"
            assert schedule.status == "uncertain"
            assert content.status == "uncertain"
            events = (await db.scalars(select(BrowserEvent))).all()
            assert events[-1].event_type == "JOB_UNKNOWN"
            try:
                await recover_stale_browser_jobs(db, now=datetime.now(UTC))
            except Exception as exc:  # pragma: no cover - explicit regression guard
                raise AssertionError(f"stale recovery must be repeatable: {exc}") from exc

    run_async(_run())
