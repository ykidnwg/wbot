"""Tests for audit logs API."""

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from tests.conftest import run_async


def _create_user(email: str, password: str) -> None:
    async def _do() -> None:
        async with SessionLocal() as db_session:
            db_session.add(User(email=email, password_hash=hash_password(password), is_active=True))
            await db_session.commit()

    run_async(_do())


def _login(client: TestClient) -> None:
    _create_user("admin@example.com", "admin-password")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin-password"},
    )
    assert resp.status_code == 204


def test_audit_logs_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/audit-logs")
    assert response.status_code == 401


def test_audit_logs_returns_empty_initially(client: TestClient) -> None:
    _login(client)
    response = client.get("/api/v1/audit-logs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1


def test_settings_change_creates_audit_log(client: TestClient) -> None:
    _login(client)
    # Change a setting to trigger audit log
    client.put(
        "/api/v1/settings/generation_kill_switch",
        json={"value": "true"},
    )

    response = client.get("/api/v1/audit-logs")
    data = response.json()
    assert data["total"] >= 1
    log = data["items"][0]
    assert log["action"] == "setting_updated"
    assert log["entity_type"] == "setting"
    assert log["entity_id"] == "generation_kill_switch"


def test_audit_logs_filter_by_entity_type(client: TestClient) -> None:
    _login(client)
    client.put("/api/v1/settings/generation_kill_switch", json={"value": "true"})

    # Filter by entity_type
    response = client.get("/api/v1/audit-logs?entity_type=setting")
    data = response.json()
    assert data["total"] >= 1

    # Filter by non-existent type
    response = client.get("/api/v1/audit-logs?entity_type=nonexistent")
    assert response.json()["total"] == 0


def test_audit_logs_pagination(client: TestClient) -> None:
    _login(client)
    response = client.get("/api/v1/audit-logs?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
