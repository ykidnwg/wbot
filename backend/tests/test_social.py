"""Meta OAuth security, target ownership, and persona assignment coverage."""

import base64
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.social import SocialTarget
from app.services.social_security import (
    decrypt_token,
    encrypt_token,
    hash_oauth_state,
    new_oauth_state,
    token_key_is_valid,
)
from tests.conftest import run_async
from tests.test_personas import _login, _payload


def test_oauth_state_and_token_envelope_are_safe() -> None:
    raw, state_hash = new_oauth_state()
    assert raw
    assert state_hash == hash_oauth_state(raw)
    key = base64.urlsafe_b64encode(b"t" * 32).decode()
    envelope = encrypt_token("page-secret", key)
    assert "page-secret" not in envelope
    assert decrypt_token(envelope, key) == "page-secret"
    assert token_key_is_valid(key)
    assert not token_key_is_valid(None)


def test_facebook_status_and_missing_credentials_are_honest(client: TestClient) -> None:
    _login(client)
    status = client.get("/api/v1/social/provider-status")
    assert status.status_code == 200
    assert status.json()["status"] == "NEEDS_CREDENTIALS"
    start = client.get("/api/v1/social/oauth/facebook/start")
    assert start.status_code == 503
    assert start.json()["detail"] == "NEEDS_CREDENTIALS"


def test_targets_are_owner_scoped_and_assignment_requires_approved_persona(
    client: TestClient,
) -> None:
    _login(client)
    persona = client.post("/api/v1/personas", json=_payload()).json()
    assert client.post(f"/api/v1/personas/{persona['id']}/approve").status_code == 200

    async def seed_target() -> str:
        from sqlalchemy import select

        from app.models.user import User

        async with SessionLocal() as db:
            owner = await db.scalar(select(User).where(User.email == "persona@example.com"))
            assert owner is not None
            target = SocialTarget(
                owner_id=owner.id,
                connection_id=uuid4(),
                platform="facebook",
                external_target_id="page-1",
                display_name="Test Page",
                encrypted_access_token="test-only",
                metadata_json={},
            )
            # The target's connection must exist for the FK relationship.
            from app.models.social import SocialConnection

            db.add(
                SocialConnection(
                    id=target.connection_id,
                    owner_id=owner.id,
                    platform="facebook",
                    external_account_id="user-1",
                    display_name="Test User",
                    encrypted_access_token="test-only",
                )
            )
            db.add(target)
            await db.commit()
            return str(target.id)

    target_id = run_async(seed_target())
    assigned = client.post(
        f"/api/v1/social/targets/{target_id}/assignment",
        json={"persona_id": persona["id"]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["active"] is True
    assigned_target = client.get("/api/v1/social/targets").json()["items"][0]
    assert assigned_target["assigned_persona_id"] == persona["id"]

    _login(client, "other@example.com", "other-secret")
    assert client.get("/api/v1/social/targets").json()["total"] == 0
    assert (
        client.post(
            f"/api/v1/social/targets/{target_id}/assignment",
            json={"persona_id": persona["id"]},
        ).status_code
        == 409
    )
