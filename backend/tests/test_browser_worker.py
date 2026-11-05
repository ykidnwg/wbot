"""Browser worker lifecycle, safe outcomes, and encrypted login capture."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.browser.adapters import BrowserOutcome
from app.browser.worker import run_browser_worker_cycle
from app.db.session import SessionLocal
from app.models.browser import BrowserAccount, BrowserEvent, BrowserJob, BrowserProfile
from app.models.content import ContentItem
from app.services.browser import claim_due_browser_jobs
from app.services.social_security import decrypt_token
from tests.conftest import run_async
from tests.test_browser import (
    SESSION_STATE,
    TEST_KEY,
    _activate_account,
    _approved_content,
    _create_account,
)
from tests.test_personas import _login


class FakeSession:
    def __init__(self, state: dict[str, object]) -> None:
        self.page = object()
        self.state = state
        self.closed = False

    async def storage_state(self) -> dict[str, object]:
        return self.state

    async def close(self) -> None:
        self.closed = True


class FakeRuntime:
    def __init__(self, state: dict[str, object] | None = None) -> None:
        self.state = state or SESSION_STATE
        self.started = False
        self.closed = False
        self.received_state: dict[str, object] | None = None
        self.session: FakeSession | None = None

    async def start(self) -> None:
        self.started = True

    async def new_session(
        self, *, storage_state: dict[str, object] | None = None
    ) -> FakeSession:
        self.received_state = storage_state
        self.session = FakeSession(self.state)
        return self.session

    async def close(self) -> None:
        self.closed = True


class FakeAdapter:
    platform = "facebook"

    def __init__(
        self,
        *,
        publish: BrowserOutcome | None = None,
        login: BrowserOutcome | None = None,
        check: BrowserOutcome | None = None,
        raise_on_publish: bool = False,
    ) -> None:
        self.publish_result = publish or BrowserOutcome(
            status="SUCCESS", message="Published", external_post_id="fb-123"
        )
        self.login_result = login or BrowserOutcome(status="SUCCESS", message="Session captured")
        self.check_result = check or BrowserOutcome(status="SUCCESS", message="Session is healthy")
        self.raise_on_publish = raise_on_publish
        self.publish_calls = 0

    async def publish(self, session: object, **_: object) -> BrowserOutcome:
        del session
        self.publish_calls += 1
        if self.raise_on_publish:
            raise RuntimeError("browser disconnected after submit")
        return self.publish_result

    async def login(self, session: object, **_: object) -> BrowserOutcome:
        del session
        return self.login_result

    async def check_session(self, session: object, **_: object) -> BrowserOutcome:
        del session
        return self.check_result


def _create_publish_job(client: TestClient, content_id: str, account_id: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/browser/jobs",
        json={
            "account_id": account_id,
            "content_item_id": content_id,
            "job_type": "PUBLISH",
            "idempotency_key": f"browser-worker-{content_id[:8]}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_worker_publishes_job_and_records_safe_events(client: TestClient) -> None:
    _login(client)
    content_id = _approved_content(client)
    account = _create_account(client)
    _activate_account(account["id"], SESSION_STATE)
    job = _create_publish_job(client, content_id, account["id"])

    async def _run() -> None:
        async with SessionLocal() as db:
            result = await run_browser_worker_cycle(
                db,
                runtime=FakeRuntime(),
                adapters={"facebook": FakeAdapter()},
                worker_id="test-worker",
                now=datetime.now(UTC),
            )
            assert result.succeeded == 1
            await db.commit()
            stored = await db.get(BrowserJob, UUID(str(job["id"])))
            content = await db.get(ContentItem, UUID(content_id))
            assert stored is not None and stored.status == "SUCCESS"
            assert stored.external_post_id == "fb-123"
            assert content is not None and content.status == "published"
            events = (
                await db.scalars(
                    select(BrowserEvent)
                    .where(BrowserEvent.browser_job_id == stored.id)
                    .order_by(BrowserEvent.created_at.asc())
                )
            ).all()
            assert [event.event_type for event in events] == [
                "JOB_QUEUED",
                "JOB_STARTED",
                "JOB_SUCCESS",
            ]
            assert all("secret-cookie-value" not in event.message for event in events)

    run_async(_run())


def test_worker_requires_intervention_when_session_is_missing(client: TestClient) -> None:
    _login(client)
    content_id = _approved_content(client)
    account = _create_account(client)

    async def _activate_without_session() -> None:
        async with SessionLocal() as db:
            stored = await db.get(BrowserAccount, UUID(str(account["id"])))
            assert stored is not None
            stored.status = "ACTIVE"
            await db.commit()

    run_async(_activate_without_session())
    job = _create_publish_job(client, content_id, account["id"])

    async def _run() -> None:
        async with SessionLocal() as db:
            runtime = FakeRuntime()
            result = await run_browser_worker_cycle(
                db,
                runtime=runtime,
                adapters={"facebook": FakeAdapter()},
                worker_id="test-worker",
                now=datetime.now(UTC),
            )
            assert result.needs_user_action == 1
            await db.commit()
            stored = await db.get(BrowserJob, UUID(str(job["id"])))
            account_row = await db.get(BrowserAccount, UUID(str(account["id"])))
            assert stored is not None and stored.status == "NEEDS_USER_ACTION"
            assert account_row is not None
            assert account_row.status == "NEEDS_REAUTHENTICATION"
            assert runtime.received_state is None

    run_async(_run())


def test_ambiguous_publish_failure_is_unknown_and_not_retried(client: TestClient) -> None:
    _login(client)
    content_id = _approved_content(client)
    account = _create_account(client)
    _activate_account(account["id"], SESSION_STATE)
    job = _create_publish_job(client, content_id, account["id"])

    async def _run() -> None:
        async with SessionLocal() as db:
            adapter = FakeAdapter(raise_on_publish=True)
            result = await run_browser_worker_cycle(
                db,
                runtime=FakeRuntime(),
                adapters={"facebook": adapter},
                worker_id="test-worker",
                now=datetime.now(UTC),
            )
            assert result.unknown == 1
            assert adapter.publish_calls == 1
            await db.commit()
            stored = await db.get(BrowserJob, UUID(str(job["id"])))
            content = await db.get(ContentItem, UUID(content_id))
            assert stored is not None and stored.status == "UNKNOWN"
            assert content is not None and content.status == "uncertain"

    run_async(_run())
    retry = client.post(f"/api/v1/browser/jobs/{job['id']}/retry")
    assert retry.status_code == 409


def test_login_job_saves_encrypted_state_and_activates_account(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(client)
    account = _create_account(client)
    login = client.post(f"/api/v1/browser/accounts/{account['id']}/login")
    assert login.status_code == 201, login.text

    async def _run() -> None:
        async with SessionLocal() as db:
            result = await run_browser_worker_cycle(
                db,
                runtime=FakeRuntime(state=SESSION_STATE),
                adapters={"facebook": FakeAdapter()},
                worker_id="test-worker",
                now=datetime.now(UTC),
            )
            assert result.succeeded == 1
            await db.commit()
            stored = await db.get(BrowserJob, UUID(str(login.json()["id"])))
            account_row = await db.get(BrowserAccount, UUID(str(account["id"])))
            profile = await db.scalar(select(BrowserProfile))
            assert stored is not None and stored.status == "SUCCESS"
            assert account_row is not None and account_row.status == "ACTIVE"
            assert profile is not None and profile.encrypted_storage_state is not None
            assert "secret-cookie-value" not in profile.encrypted_storage_state
            assert json.loads(
                decrypt_token(profile.encrypted_storage_state, TEST_KEY)
            ) == SESSION_STATE
            assert "secret-cookie-value" not in str(stored.result_json)

    monkeypatch.setattr(
        "app.browser.worker.get_settings",
        lambda: type(
            "WorkerSettings",
            (),
            {
                "token_encryption_key": TEST_KEY,
                "browser_login_timeout_seconds": 1,
                "browser_headless": False,
            },
        )(),
    )
    run_async(_run())


def test_account_claim_is_serialized(client: TestClient) -> None:
    _login(client)
    first_content = _approved_content(client, "First browser post")
    second_content = _approved_content(client, "Second browser post")
    account = _create_account(client)
    _activate_account(account["id"], SESSION_STATE)
    _create_publish_job(client, first_content, account["id"])
    _create_publish_job(client, second_content, account["id"])

    async def _run() -> None:
        async with SessionLocal() as db:
            claimed = await claim_due_browser_jobs(
                db, now=datetime.now(UTC) + timedelta(minutes=1), worker_id="test-worker"
            )
            assert len(claimed) == 1
            assert await claim_due_browser_jobs(
                db, now=datetime.now(UTC) + timedelta(minutes=1), worker_id="other-worker"
            ) == []

    run_async(_run())
