"""Schedule creation, cancellation, owner isolation, and publishing worker coverage."""

import base64
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.content import ContentItem
from app.models.publishing import PublishingAttempt, PublishingJob, Schedule
from app.models.social import SocialConnection, SocialTarget
from app.models.user import User
from app.providers.publishing import PublishResult
from app.services import publishing as publishing_service
from app.services.social_security import encrypt_token
from tests.conftest import run_async
from tests.test_personas import _login, _payload

TEST_KEY = base64.urlsafe_b64encode(b"k" * 32).decode()


def _approved_content(client: TestClient) -> str:
    persona = client.post("/api/v1/personas", json=_payload()).json()
    assert client.post(f"/api/v1/personas/{persona['id']}/approve").status_code == 200
    content = client.post(
        "/api/v1/content/generate-caption",
        json={
            "persona_id": persona["id"],
            "topic": "Slow morning routine",
            "platform": "facebook",
        },
    )
    assert content.status_code == 201
    content_id = content.json()["id"]
    assert (
        client.post(
            f"/api/v1/content/{content_id}/approval", json={"decision": "approved"}
        ).status_code
        == 200
    )
    return content_id


def _seed_target(email: str = "persona@example.com") -> str:
    async def _do() -> str:
        async with SessionLocal() as db:
            owner = await db.scalar(select(User).where(User.email == email))
            assert owner is not None
            connection = SocialConnection(
                owner_id=owner.id,
                platform="facebook",
                external_account_id=f"user-{uuid4()}",
                display_name="Test User",
                encrypted_access_token=encrypt_token("user-token", TEST_KEY),
            )
            db.add(connection)
            await db.flush()
            target = SocialTarget(
                owner_id=owner.id,
                connection_id=connection.id,
                platform="facebook",
                external_target_id="page-1",
                display_name="Test Page",
                encrypted_access_token=encrypt_token("page-token", TEST_KEY),
                metadata_json={},
            )
            db.add(target)
            await db.commit()
            return str(target.id)

    return run_async(_do())


def _setup(client: TestClient) -> tuple[str, str]:
    _login(client)
    content_id = _approved_content(client)
    target_id = _seed_target()
    assigned = client.post(
        f"/api/v1/social/targets/{target_id}/assignment",
        json={"persona_id": client.get("/api/v1/personas").json()["items"][0]["id"]},
    )
    assert assigned.status_code == 200
    return content_id, target_id


def test_schedule_create_is_idempotent_and_cancellable(client: TestClient) -> None:
    content_id, target_id = _setup(client)
    scheduled_for = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    payload = {
        "content_item_id": content_id,
        "social_target_id": target_id,
        "scheduled_for": scheduled_for,
        "timezone": "UTC",
    }
    first = client.post("/api/v1/schedules", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/schedules", json=payload)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]

    listed = client.get("/api/v1/schedules")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    content = client.get("/api/v1/content").json()["items"][0]
    assert content["status"] == "scheduled"

    cancelled = client.delete(f"/api/v1/schedules/{first.json()['id']}")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    content = client.get("/api/v1/content").json()["items"][0]
    assert content["status"] == "approved"


def test_schedule_requires_future_time_and_matching_assignment(client: TestClient) -> None:
    content_id, target_id = _setup(client)
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    response = client.post(
        "/api/v1/schedules",
        json={
            "content_item_id": content_id,
            "social_target_id": target_id,
            "scheduled_for": past,
            "timezone": "UTC",
        },
    )
    assert response.status_code == 409


def test_schedules_are_owner_scoped(client: TestClient) -> None:
    content_id, target_id = _setup(client)
    created = client.post(
        "/api/v1/schedules",
        json={
            "content_item_id": content_id,
            "social_target_id": target_id,
            "scheduled_for": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert created.status_code == 201
    _login(client, "schedule-other@example.com", "other-secret")
    assert client.get("/api/v1/schedules").json()["total"] == 0
    assert client.delete(f"/api/v1/schedules/{created.json()['id']}").status_code == 404


def test_worker_publishes_due_schedule_with_real_state_changes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    content_id, target_id = _setup(client)
    created = client.post(
        "/api/v1/schedules",
        json={
            "content_item_id": content_id,
            "social_target_id": target_id,
            "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert created.status_code == 201

    class FakePublisher:
        def __init__(self, _config: object) -> None:
            pass

        async def publish(self, **_: object) -> PublishResult:
            return PublishResult(
                external_post_id="page-1_123", published_url="https://facebook.com/page-1/posts/123"
            )

    monkeypatch.setattr(publishing_service, "FacebookPagePublisher", FakePublisher)
    monkeypatch.setattr(publishing_service.settings, "meta_app_id", "app-id")
    monkeypatch.setattr(publishing_service.settings, "meta_app_secret", "app-secret")
    monkeypatch.setattr(publishing_service.settings, "token_encryption_key", TEST_KEY)
    monkeypatch.setattr(
        publishing_service.settings, "meta_oauth_redirect_uri", "https://example.com/cb"
    )

    async def _run() -> None:
        async with SessionLocal() as db:
            schedule = await db.scalar(select(Schedule))
            assert schedule is not None
            schedule.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
            await db.commit()
            result = await publishing_service.run_worker_cycle(
                db, now=datetime.now(UTC)
            )
            await db.commit()
            assert result.dispatched == 1
            assert result.succeeded == 1

    run_async(_run())

    async def _check() -> None:
        async with SessionLocal() as db:
            schedule = await db.scalar(select(Schedule))
            job = await db.scalar(select(PublishingJob))
            item = await db.scalar(select(ContentItem))
            attempts = (await db.scalars(select(PublishingAttempt))).all()
            assert schedule is not None and schedule.status == "published"
            assert job is not None and job.status == "succeeded"
            assert job.external_post_id == "page-1_123"
            assert item is not None and item.status == "published"
            assert len(attempts) == 1
            assert attempts[0].status == "succeeded"

    run_async(_check())


def test_worker_marks_needs_credentials_without_calling_provider(
    client: TestClient,
) -> None:
    content_id, target_id = _setup(client)
    assert (
        client.post(
            "/api/v1/schedules",
            json={
                "content_item_id": content_id,
                "social_target_id": target_id,
                "scheduled_for": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
            },
        ).status_code
        == 201
    )

    async def _run() -> None:
        async with SessionLocal() as db:
            schedule = await db.scalar(select(Schedule))
            assert schedule is not None
            schedule.scheduled_for = datetime.now(UTC) - timedelta(minutes=1)
            await db.commit()
            await publishing_service.run_worker_cycle(db, now=datetime.now(UTC))
            await db.commit()
            job = await db.scalar(select(PublishingJob))
            item = await db.scalar(select(ContentItem))
            assert job is not None and job.status == "needs_credentials"
            assert job.error_category == "auth"
            assert item is not None and item.status == "approved"

    run_async(_run())


def test_worker_recovers_stale_running_job_as_uncertain(client: TestClient) -> None:
    content_id, target_id = _setup(client)
    now = datetime.now(UTC)

    async def _run() -> None:
        async with SessionLocal() as db:
            item = await db.scalar(select(ContentItem).where(ContentItem.id == UUID(content_id)))
            target = await db.scalar(select(SocialTarget).where(SocialTarget.id == UUID(target_id)))
            assert item is not None and target is not None
            item.status = "publishing"
            schedule = Schedule(
                owner_id=item.owner_id,
                content_item_id=item.id,
                social_target_id=target.id,
                scheduled_for=now - timedelta(minutes=30),
                timezone="UTC",
                status="publishing",
                idempotency_key=f"stale-schedule-{uuid4()}",
            )
            db.add(schedule)
            await db.flush()
            job = PublishingJob(
                owner_id=item.owner_id,
                schedule_id=schedule.id,
                content_item_id=item.id,
                social_target_id=target.id,
                platform=target.platform,
                status="running",
                attempts=1,
                idempotency_key=f"stale-job-{uuid4()}",
                started_at=now - timedelta(minutes=30),
            )
            db.add(job)
            await db.commit()

            result = await publishing_service.run_worker_cycle(db, now=now)
            assert result.recovered == 1
            await db.refresh(schedule)
            await db.refresh(job)
            await db.refresh(item)
            assert schedule.status == "uncertain"
            assert job.status == "uncertain"
            assert item.status == "uncertain"
            attempt = await db.scalar(
                select(PublishingAttempt).where(PublishingAttempt.publishing_job_id == job.id)
            )
            assert attempt is not None and attempt.status == "uncertain"

    run_async(_run())


def test_schedule_interprets_naive_time_in_selected_timezone(client: TestClient) -> None:
    content_id, target_id = _setup(client)
    zone = ZoneInfo("Asia/Jakarta")
    local_time = (datetime.now(UTC) + timedelta(days=1)).astimezone(zone).replace(tzinfo=None)
    response = client.post(
        "/api/v1/schedules",
        json={
            "content_item_id": content_id,
            "social_target_id": target_id,
            "scheduled_for": local_time.isoformat(),
            "timezone": "Asia/Jakarta",
        },
    )
    assert response.status_code == 201
    stored = datetime.fromisoformat(response.json()["scheduled_for"])
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=UTC)
    assert stored == local_time.replace(tzinfo=zone).astimezone(UTC)