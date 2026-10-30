"""Persona ownership, adult-only validation, and immutable approval behavior."""

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


def _login(
    client: TestClient, email: str = "persona@example.com", password: str = "secret"
) -> None:
    _create_user(email, password)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 204


def _payload(age: int = 28) -> dict[str, object]:
    return {
        "name": "Nadia",
        "age": age,
        "language": "Bahasa Indonesia",
        "personality": "Ramah dan menyukai fashion berkelanjutan.",
        "target_audience": "Dewasa yang tertarik pada lifestyle.",
        "clothing_style": "Casual modest fashion.",
        "identity_description": "Karakter fiktif dewasa untuk konten lifestyle.",
        "caption_preferences": {"style": "santai", "disclosure": ""},
        "prompt_version": "persona-v1",
    }


def test_persona_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/personas").status_code == 401


def test_personas_only_allow_adults(client: TestClient) -> None:
    _login(client)
    response = client.post("/api/v1/personas", json=_payload(age=17))
    assert response.status_code == 422


def test_approval_creates_immutable_version(client: TestClient) -> None:
    _login(client)
    created = client.post("/api/v1/personas", json=_payload())
    assert created.status_code == 201
    persona = created.json()

    approved = client.post(f"/api/v1/personas/{persona['id']}/approve")
    assert approved.status_code == 200
    version = approved.json()
    assert version["version_no"] == 1
    assert version["age"] == 28

    update = client.put(f"/api/v1/personas/{persona['id']}", json=_payload())
    assert update.status_code == 409
    history = client.get(f"/api/v1/personas/{persona['id']}/versions")
    assert history.status_code == 200
    assert len(history.json()) == 1


def test_persona_isolation_by_owner(client: TestClient) -> None:
    _login(client)
    created = client.post("/api/v1/personas", json=_payload())
    persona_id = created.json()["id"]

    _login(client, "other@example.com", "other-secret")
    assert client.get(f"/api/v1/personas/{persona_id}").status_code == 404
    assert client.get("/api/v1/personas").json()["total"] == 0


def test_bulk_batch_resumes_approves_only_selected_and_regeneration_is_honest(
    client: TestClient,
) -> None:
    _login(client)
    first = _payload()
    first["name"] = "Candidate One"
    second = _payload()
    second["name"] = "Candidate Two"
    response = client.post(
        "/api/v1/personas/batches",
        json={
            "name": "Lifestyle April",
            "candidates": [
                {**first, "target_label": "Facebook · Lifestyle"},
                {**second, "target_label": "Instagram · Fashion"},
            ],
        },
    )
    assert response.status_code == 201
    batch = response.json()
    assert batch["candidate_count"] == 2
    assert {item["target_label"] for item in batch["candidates"]} == {
        "Facebook · Lifestyle",
        "Instagram · Fashion",
    }

    selected_id = batch["candidates"][0]["id"]
    approved = client.post(
        f"/api/v1/personas/batches/{batch['id']}/approve-selected",
        json={"candidate_ids": [selected_id]},
    )
    assert approved.status_code == 200
    assert approved.json()["approved_count"] == 1

    resumed = client.get(f"/api/v1/personas/batches/{batch['id']}").json()
    statuses = {item["name"]: item["status"] for item in resumed["candidates"]}
    assert statuses == {"Candidate One": "approved", "Candidate Two": "draft"}

    unselected = next(item for item in resumed["candidates"] if item["status"] == "draft")
    unselected_id = unselected["id"]
    regenerate = client.post(
        f"/api/v1/personas/batches/{batch['id']}/candidates/{unselected_id}/regenerate"
    )
    assert regenerate.status_code == 503
    assert "NEEDS_CREDENTIALS" in regenerate.json()["detail"]
    after_regenerate = client.get(f"/api/v1/personas/batches/{batch['id']}").json()
    after_candidate = next(
        item for item in after_regenerate["candidates"] if item["id"] == unselected_id
    )
    assert after_candidate["status"] == "draft"

    _login(client, "batch-owner@example.com", "other-secret")
    assert client.get(f"/api/v1/personas/batches/{batch['id']}").status_code == 404
