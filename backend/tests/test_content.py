"""Content draft provider disclosure, approval gates, and owner isolation."""

from fastapi.testclient import TestClient

from tests.test_personas import _login, _payload


def _approved_persona(client: TestClient) -> str:
    created = client.post("/api/v1/personas", json=_payload())
    assert created.status_code == 201
    persona_id = created.json()["id"]
    approved = client.post(f"/api/v1/personas/{persona_id}/approve")
    assert approved.status_code == 200
    return persona_id


def test_mock_caption_draft_requires_approved_persona_and_explicit_approval(
    client: TestClient,
) -> None:
    _login(client)
    draft_persona = client.post("/api/v1/personas", json=_payload()).json()
    blocked = client.post(
        "/api/v1/content/generate-caption",
        json={"persona_id": draft_persona["id"], "topic": "Jalan pagi"},
    )
    assert blocked.status_code == 409

    persona_id = _approved_persona(client)
    generated = client.post(
        "/api/v1/content/generate-caption",
        json={"persona_id": persona_id, "topic": "Gaya santai akhir pekan", "platform": "facebook"},
    )
    assert generated.status_code == 201
    item = generated.json()
    assert item["provider"] == "mock/template-v1"
    assert item["status"] == "draft"
    assert "Gaya santai akhir pekan" in item["caption"]

    listed = client.get("/api/v1/content")
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == item["id"]

    approved = client.post(f"/api/v1/content/{item['id']}/approval", json={"decision": "approved"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    repeated = client.post(f"/api/v1/content/{item['id']}/approval", json={"decision": "approved"})
    assert repeated.status_code == 409

    revised_caption = "Gaya santai akhir pekan, versi yang sudah diperbarui."
    revised = client.put(
        f"/api/v1/content/{item['id']}/caption", json={"caption": revised_caption}
    )
    assert revised.status_code == 200
    assert revised.json()["status"] == "draft"
    assert revised.json()["version_no"] == 2
    assert revised.json()["caption"] == revised_caption

    versions = client.get(f"/api/v1/content/{item['id']}/versions")
    assert versions.status_code == 200
    assert [version["version_no"] for version in versions.json()] == [2, 1]
    assert versions.json()[1]["caption"] == item["caption"]

    reapproved = client.post(
        f"/api/v1/content/{item['id']}/approval", json={"decision": "approved"}
    )
    assert reapproved.status_code == 200
    assert reapproved.json()["status"] == "approved"


def test_content_and_persona_are_scoped_to_owner(client: TestClient) -> None:
    _login(client)
    persona_id = _approved_persona(client)
    created = client.post(
        "/api/v1/content/generate-caption",
        json={"persona_id": persona_id, "topic": "Hari yang cerah"},
    )
    content_id = created.json()["id"]

    _login(client, "content-other@example.com", "other-secret")
    assert client.get("/api/v1/content").json()["total"] == 0
    assert (
        client.post(
            f"/api/v1/content/{content_id}/approval", json={"decision": "approved"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/content/generate-caption",
            json={"persona_id": persona_id, "topic": "Tidak boleh lintas pemilik"},
        ).status_code
        == 409
    )
