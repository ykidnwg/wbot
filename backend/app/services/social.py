"""Social account, OAuth, target synchronization, and persona assignment use cases."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.persona import Persona
from app.models.social import OAuthState, PersonaAssignment, SocialConnection, SocialTarget
from app.providers.meta import MetaAdapter, MetaConfig
from app.services.social_security import (
    constant_time_equal,
    encrypt_token,
    hash_oauth_state,
    new_oauth_state,
    oauth_expiry,
)

META_PERMISSIONS = [
    "pages_show_list",
    "pages_manage_metadata",
    "pages_manage_posts",
    "pages_manage_read_engagement",
]


def meta_config(settings: Settings) -> MetaConfig | None:
    app_id = settings.meta_app_id
    app_secret = settings.meta_app_secret
    redirect_uri = settings.meta_oauth_redirect_uri
    if not all((app_id, app_secret, redirect_uri, settings.token_encryption_key)):
        return None
    assert app_id is not None
    assert app_secret is not None
    assert redirect_uri is not None
    return MetaConfig(
        app_id=app_id,
        app_secret=app_secret,
        graph_api_version=settings.meta_graph_api_version,
        redirect_uri=redirect_uri,
    )


async def create_oauth_state(
    db: AsyncSession, owner_id: UUID, redirect_uri: str
) -> tuple[str, datetime]:
    raw_state, state_hash = new_oauth_state()
    expires_at = oauth_expiry()
    db.add(
        OAuthState(
            owner_id=owner_id,
            provider="facebook",
            state_hash=state_hash,
            redirect_uri=redirect_uri,
            expires_at=expires_at,
        )
    )
    await db.flush()
    return raw_state, expires_at


async def consume_oauth_state(
    db: AsyncSession, owner_id: UUID, raw_state: str, redirect_uri: str
) -> OAuthState | None:
    state = await db.scalar(
        select(OAuthState)
        .where(
            OAuthState.owner_id == owner_id,
            OAuthState.provider == "facebook",
            OAuthState.redirect_uri == redirect_uri,
            OAuthState.expires_at > datetime.now(UTC),
            OAuthState.consumed_at.is_(None),
        )
        .with_for_update()
    )
    if state is None or not constant_time_equal(state.state_hash, hash_oauth_state(raw_state)):
        return None
    state.consumed_at = datetime.now(UTC)
    await db.flush()
    return state


async def sync_pages(
    db: AsyncSession,
    owner_id: UUID,
    settings: Settings,
    adapter: MetaAdapter,
    code: str,
    redirect_uri: str,
) -> SocialConnection:
    if not settings.token_encryption_key:
        raise ValueError("Social token encryption is not configured")
    user_token = await adapter.exchange_code(code, redirect_uri)
    user = await adapter.get_user(user_token)
    pages = await adapter.list_pages(user_token)
    connection = await db.scalar(
        select(SocialConnection).where(
            SocialConnection.owner_id == owner_id,
            SocialConnection.platform == "facebook",
            SocialConnection.external_account_id == user.external_id,
        )
    )
    if connection is None:
        connection = SocialConnection(
            owner_id=owner_id,
            platform="facebook",
            external_account_id=user.external_id,
            display_name=user.name,
            encrypted_access_token=encrypt_token(user_token, settings.token_encryption_key),
        )
        db.add(connection)
        await db.flush()
    else:
        connection.display_name = user.name
        connection.encrypted_access_token = encrypt_token(
            user_token, settings.token_encryption_key
        )
        connection.status = "connected"
        connection.error_message = None
    now = datetime.now(UTC)
    connection.last_synced_at = now
    for page in pages:
        target = await db.scalar(
            select(SocialTarget).where(
                SocialTarget.owner_id == owner_id,
                SocialTarget.connection_id == connection.id,
                SocialTarget.external_target_id == page.external_id,
            )
        )
        values = {
            "display_name": page.name,
            "username": page.username,
            "profile_image_url": page.profile_image_url,
            "encrypted_access_token": encrypt_token(
                page.access_token, settings.token_encryption_key
            ),
            "metadata_json": page.metadata,
            "status": "active",
            "last_synced_at": now,
        }
        if target is None:
            db.add(
                SocialTarget(
                    owner_id=owner_id,
                    connection_id=connection.id,
                    platform="facebook",
                    external_target_id=page.external_id,
                    **values,
                )
            )
        else:
            for key, value in values.items():
                setattr(target, key, value)
    await db.flush()
    await db.refresh(connection)
    return connection


async def list_connections(
    db: AsyncSession, owner_id: UUID, page: int, page_size: int
) -> tuple[list[SocialConnection], int]:
    base = select(SocialConnection).where(SocialConnection.owner_id == owner_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await db.scalars(
        base.order_by(SocialConnection.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.all()), total


async def list_targets(
    db: AsyncSession, owner_id: UUID, page: int, page_size: int
) -> tuple[list[SocialTarget], int]:
    base = select(SocialTarget).where(SocialTarget.owner_id == owner_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = await db.scalars(
        base.order_by(SocialTarget.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(rows.all()), total


async def assign_persona(
    db: AsyncSession, owner_id: UUID, target_id: UUID, persona_id: UUID
) -> PersonaAssignment:
    target = await db.scalar(
        select(SocialTarget).where(
            SocialTarget.id == target_id,
            SocialTarget.owner_id == owner_id,
            SocialTarget.status == "active",
        )
    )
    persona = await db.scalar(
        select(Persona).where(
            Persona.id == persona_id,
            Persona.owner_id == owner_id,
            Persona.status == "approved",
        )
    )
    if target is None or persona is None:
        raise ValueError("An owned active target and approved persona are required")
    assignment = await db.scalar(
        select(PersonaAssignment)
        .where(
            PersonaAssignment.owner_id == owner_id,
            PersonaAssignment.social_target_id == target_id,
        )
        .with_for_update()
    )
    now = datetime.now(UTC)
    if assignment is None:
        assignment = PersonaAssignment(
            owner_id=owner_id,
            social_target_id=target_id,
            persona_id=persona_id,
            active=True,
        )
        db.add(assignment)
    else:
        assignment.persona_id = persona_id
        assignment.active = True
        assignment.removed_at = None
        assignment.assigned_at = now
    await db.flush()
    await db.refresh(assignment)
    return assignment


async def remove_assignment(
    db: AsyncSession, owner_id: UUID, target_id: UUID
) -> PersonaAssignment | None:
    assignment = await db.scalar(
        select(PersonaAssignment)
        .where(
            PersonaAssignment.owner_id == owner_id,
            PersonaAssignment.social_target_id == target_id,
            PersonaAssignment.active.is_(True),
        )
        .with_for_update()
    )
    if assignment is None:
        return None
    assignment.active = False
    assignment.removed_at = datetime.now(UTC)
    await db.flush()
    return assignment
