"""Tests for notifications API."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.notification import Notification
from app.models.user import User
from tests.conftest import run_async


def _create_user_and_get_id(email: str, password: str) -> UUID:
    user_id = uuid4()

    async def _do() -> None:
        async with SessionLocal() as db_session:
            db_session.add(
                User(
                    id=user_id,
                    email=email,
                    password_hash=hash_password(password),
                    is_active=True,
                )
            )
            await db_session.commit()

    run_async(_do())
    return user_id


def _login(client: TestClient) -> UUID:
    user_id = _create_user_and_get_id("admin@example.com", "admin-password")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin-password"},
    )
    assert resp.status_code == 204
    return user_id


def _add_notification(owner_id: UUID, title: str, message: str) -> UUID:
    notification_id = uuid4()

    async def _do() -> None:
        async with SessionLocal() as db_session:
            db_session.add(
                Notification(
                    id=notification_id,
                    owner_id=owner_id,
                    title=title,
                    message=message,
                    level="info",
                )
            )
            await db_session.commit()

    run_async(_do())
    return notification_id


def test_notifications_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/notifications")
    assert response.status_code == 401


def test_notifications_returns_empty_initially(client: TestClient) -> None:
    _login(client)
    response = client.get("/api/v1/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["unread_count"] == 0


def test_notifications_returns_user_items(client: TestClient) -> None:
    user_id = _login(client)
    _add_notification(user_id, "Test", "Test notification")

    response = client.get("/api/v1/notifications")
    data = response.json()
    assert len(data["items"]) == 1
    assert data["unread_count"] == 1
    assert data["items"][0]["title"] == "Test"


def test_mark_notifications_read(client: TestClient) -> None:
    user_id = _login(client)
    n_id = _add_notification(user_id, "Read me", "Please read")

    # Mark as read
    response = client.post(
        "/api/v1/notifications/mark-read",
        json={"notification_ids": [str(n_id)]},
    )
    assert response.status_code == 204

    # Verify unread count is 0
    get_response = client.get("/api/v1/notifications")
    assert get_response.json()["unread_count"] == 0


def test_notifications_filter_unread(client: TestClient) -> None:
    user_id = _login(client)
    n_id = _add_notification(user_id, "Unread 1", "msg1")
    _add_notification(user_id, "Unread 2", "msg2")

    # Mark one as read
    client.post(
        "/api/v1/notifications/mark-read",
        json={"notification_ids": [str(n_id)]},
    )

    response = client.get("/api/v1/notifications?unread_only=true")
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Unread 2"
