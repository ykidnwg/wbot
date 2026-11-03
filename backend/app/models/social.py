"""Owner-scoped social connections, targets, OAuth state, and persona assignments."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OAuthState(Base):
    __tablename__ = "oauth_states"
    __table_args__ = (
        CheckConstraint("provider IN ('facebook')", name="ck_oauth_states_provider"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(40))
    state_hash: Mapped[str] = mapped_column(String(64), unique=True)
    redirect_uri: Mapped[str] = mapped_column(String(1000))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialConnection(Base):
    __tablename__ = "social_connections"
    __table_args__ = (
        CheckConstraint("platform IN ('facebook')", name="ck_social_connections_platform"),
        CheckConstraint(
            "status IN ('connected', 'needs_reconnect', 'revoked', 'error')",
            name="ck_social_connections_status",
        ),
        Index(
            "uq_social_connections_owner_platform_external",
            "owner_id",
            "platform",
            "external_account_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(40))
    external_account_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="connected", server_default="connected")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SocialTarget(Base):
    __tablename__ = "social_targets"
    __table_args__ = (
        CheckConstraint("platform IN ('facebook')", name="ck_social_targets_platform"),
        CheckConstraint(
            "status IN ('active', 'needs_reconnect', 'disabled', 'error')",
            name="ck_social_targets_status",
        ),
        Index(
            "uq_social_targets_connection_external",
            "connection_id",
            "external_target_id",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("social_connections.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(40))
    external_target_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    encrypted_access_token: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="active", server_default="active")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PersonaAssignment(Base):
    __tablename__ = "persona_assignments"
    __table_args__ = (
        UniqueConstraint("owner_id", "social_target_id", name="uq_persona_assignments_target"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("personas.id", ondelete="RESTRICT"), index=True
    )
    social_target_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("social_targets.id", ondelete="CASCADE"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
