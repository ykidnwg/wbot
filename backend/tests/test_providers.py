"""Provider status and honest missing-credential behavior."""

from fastapi.testclient import TestClient

from tests.test_personas import _login, _payload


def _approved_persona(client: TestClient) -> str:
    persona = client.post("/api/v1/personas", json=_payload()).json()
    assert client.post(f"/api/v1/personas/{persona['id']}/approve").status_code == 200
    return persona["id"]


def test_default_providers_are_labeled_mock(client: TestClient) -> None:
    _login(client)
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    items = {item["kind"]: item for item in response.json()["items"]}
    assert items["caption"]["mode"] == "mock"
    assert items["image"]["mode"] == "mock"
    assert items["publishing"]["status"] == "NEEDS_CREDENTIALS"


def test_selecting_live_provider_without_key_reports_needs_credentials(
    client: TestClient,
) -> None:
    _login(client)
    assert (
        client.put("/api/v1/settings/caption_provider", json={"value": "openai"}).status_code
        == 200
    )
    status = client.get("/api/v1/providers").json()["items"]
    caption = next(item for item in status if item["kind"] == "caption")
    assert caption["status"] == "NEEDS_CREDENTIALS"

    persona_id = _approved_persona(client)
    generated = client.post(
        "/api/v1/content/generate-caption",
        json={"persona_id": persona_id, "topic": "Provider failure path"},
    )
    assert generated.status_code == 503
    assert generated.json()["detail"] == "NEEDS_CREDENTIALS"
    assert client.get("/api/v1/content").json()["total"] == 0


def test_live_image_provider_without_key_reports_needs_credentials(
    client: TestClient,
) -> None:
    _login(client)
    assert (
        client.put("/api/v1/settings/image_provider", json={"value": "openai"}).status_code
        == 200
    )
    persona_id = _approved_persona(client)
    generated = client.post(
        "/api/v1/media/generate", json={"persona_id": persona_id, "prompt": "Portrait"}
    )
    assert generated.status_code == 503
    assert generated.json()["detail"] == "NEEDS_CREDENTIALS"


def test_provider_settings_reject_invalid_values(client: TestClient) -> None:
    _login(client)
    assert (
        client.put("/api/v1/settings/caption_provider", json={"value": "unknown"}).status_code
        == 422
    )
    assert (
        client.put(
            "/api/v1/settings/openai_api_base", json={"value": "http://insecure.example"}
        ).status_code
        == 422
    )
