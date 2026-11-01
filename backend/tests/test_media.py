"""Image provider, validation, storage, and owner-isolation coverage."""

from fastapi.testclient import TestClient

from app.providers.image import MockImageProvider
from app.services.media import validate_image
from tests.test_personas import _login, _payload


def _approved_persona(client: TestClient) -> str:
    created = client.post("/api/v1/personas", json=_payload())
    assert created.status_code == 201
    persona_id = created.json()["id"]
    assert client.post(f"/api/v1/personas/{persona_id}/approve").status_code == 200
    return persona_id


def test_mock_image_provider_is_deterministic_and_valid() -> None:
    provider = MockImageProvider()
    first = provider.generate_image(prompt="sunset")
    second = provider.generate_image(prompt="sunset")
    assert first == second
    assert provider.validate_configuration()
    assert provider.get_health() == "ok"
    assert validate_image(first).width == 1


def test_image_generation_preview_delete_and_owner_isolation(client: TestClient) -> None:
    _login(client)
    persona_id = _approved_persona(client)
    generated = client.post(
        "/api/v1/media/generate", json={"persona_id": persona_id, "prompt": "A calm portrait"}
    )
    assert generated.status_code == 201
    asset = generated.json()
    assert asset["provider"] == "mock"
    assert asset["model"] == "solid-png-v1"
    assert asset["mime_type"] == "image/png"
    assert asset["width"] == 1
    assert client.get("/api/v1/media").json()["total"] == 1
    preview = client.get(f"/api/v1/media/{asset['id']}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content.startswith(b"\x89PNG")

    _login(client, "media-other@example.com", "other-secret")
    assert client.get("/api/v1/media").json()["total"] == 0
    assert client.get(f"/api/v1/media/{asset['id']}/preview").status_code == 404
    assert client.delete(f"/api/v1/media/{asset['id']}").status_code == 404


def test_image_generation_requires_owned_approved_persona(client: TestClient) -> None:
    _login(client)
    draft = client.post("/api/v1/personas", json=_payload()).json()
    response = client.post(
        "/api/v1/media/generate", json={"persona_id": draft["id"], "prompt": "Not ready"}
    )
    assert response.status_code == 409
