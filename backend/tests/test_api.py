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


def test_liveness_and_readiness(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200


def test_login_creates_hashed_server_session_and_dashboard_is_empty(client: TestClient) -> None:
    _create_user("owner@example.com", "correct-password")

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "OWNER@EXAMPLE.COM", "password": "correct-password"},
    )

    assert login_response.status_code == 204
    assert login_response.content == b""
    assert "ai_social_session" in login_response.cookies

    dashboard_response = client.get("/api/v1/dashboard/summary")

    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["connected_accounts"] == 0
    assert dashboard_response.json()["estimated_ai_cost"] is None
    assert dashboard_response.json()["services"]["providers"] == "not_configured"


def test_invalid_login_has_generic_message(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "not-the-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_logout_revokes_session(client: TestClient) -> None:
    _create_user("owner@example.com", "correct-password")
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "correct-password"},
        ).status_code
        == 204
    )

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/dashboard/summary").status_code == 401
