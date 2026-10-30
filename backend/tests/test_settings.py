"""Tests for settings API."""

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


def test_list_settings_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/settings")
    assert response.status_code == 401


def test_list_settings_returns_defaults(client: TestClient) -> None:
    _login(client)
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    keys = [s["key"] for s in data["settings"]]
    assert "generation_kill_switch" in keys
    assert "publishing_kill_switch" in keys
    assert "max_generation_concurrency" in keys


def test_update_setting_value(client: TestClient) -> None:
    _login(client)
    response = client.put(
        "/api/v1/settings/generation_kill_switch",
        json={"value": "true"},
    )
    assert response.status_code == 200
    assert response.json()["value"] == "true"

    # Verify persisted
    get_response = client.get("/api/v1/settings")
    kill_switch = next(
        s for s in get_response.json()["settings"] if s["key"] == "generation_kill_switch"
    )
    assert kill_switch["value"] == "true"


def test_update_setting_validates_type(client: TestClient) -> None:
    _login(client)
    response = client.put(
        "/api/v1/settings/max_generation_concurrency",
        json={"value": "not-a-number"},
    )
    assert response.status_code == 422


def test_update_setting_rejects_operational_values_outside_bounds(client: TestClient) -> None:
    _login(client)
    response = client.put(
        "/api/v1/settings/max_generation_concurrency",
        json={"value": "1000"},
    )
    assert response.status_code == 422
    assert "between 1 and 32" in response.json()["detail"]


def test_update_setting_rejects_invalid_iana_timezone(client: TestClient) -> None:
    _login(client)
    response = client.put(
        "/api/v1/settings/default_timezone",
        json={"value": "Mars/Olympus"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Timezone must be a valid IANA timezone"


def test_update_nonexistent_setting(client: TestClient) -> None:
    _login(client)
    response = client.put(
        "/api/v1/settings/nonexistent_key",
        json={"value": "anything"},
    )
    assert response.status_code == 404
