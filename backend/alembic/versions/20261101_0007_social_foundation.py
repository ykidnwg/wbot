"""add social connections, targets, OAuth state, and persona assignments

Revision ID: 20261101_0007
Revises: 20261101_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261101_0007"
down_revision: str | Sequence[str] | None = "20261101_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("redirect_uri", sa.String(length=1000), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("provider IN ('facebook')", name="ck_oauth_states_provider"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_oauth_states_owner_id", "oauth_states", ["owner_id"])
    op.create_index("ix_oauth_states_expires_at", "oauth_states", ["expires_at"])
    op.create_table(
        "social_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("external_account_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="connected"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("platform IN ('facebook')", name="ck_social_connections_platform"),
        sa.CheckConstraint("status IN ('connected', 'needs_reconnect', 'revoked', 'error')", name="ck_social_connections_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "platform", "external_account_id", name="uq_social_connections_owner_platform_external"),
    )
    op.create_index("ix_social_connections_owner_id", "social_connections", ["owner_id"])
    op.create_table(
        "social_targets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("external_target_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("profile_image_url", sa.String(length=2000), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("platform IN ('facebook')", name="ck_social_targets_platform"),
        sa.CheckConstraint("status IN ('active', 'needs_reconnect', 'disabled', 'error')", name="ck_social_targets_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["social_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "external_target_id", name="uq_social_targets_connection_external"),
    )
    op.create_index("ix_social_targets_owner_id", "social_targets", ["owner_id"])
    op.create_index("ix_social_targets_connection_id", "social_targets", ["connection_id"])
    op.create_table(
        "persona_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("persona_id", sa.Uuid(), nullable=False),
        sa.Column("social_target_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["social_target_id"], ["social_targets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "social_target_id", name="uq_persona_assignments_target"),
    )
    op.create_index("ix_persona_assignments_owner_id", "persona_assignments", ["owner_id"])
    op.create_index("ix_persona_assignments_persona_id", "persona_assignments", ["persona_id"])
    op.create_index("ix_persona_assignments_social_target_id", "persona_assignments", ["social_target_id"])


def downgrade() -> None:
    op.drop_index("ix_persona_assignments_social_target_id", table_name="persona_assignments")
    op.drop_index("ix_persona_assignments_persona_id", table_name="persona_assignments")
    op.drop_index("ix_persona_assignments_owner_id", table_name="persona_assignments")
    op.drop_table("persona_assignments")
    op.drop_index("ix_social_targets_connection_id", table_name="social_targets")
    op.drop_index("ix_social_targets_owner_id", table_name="social_targets")
    op.drop_table("social_targets")
    op.drop_index("ix_social_connections_owner_id", table_name="social_connections")
    op.drop_table("social_connections")
    op.drop_index("ix_oauth_states_expires_at", table_name="oauth_states")
    op.drop_index("ix_oauth_states_owner_id", table_name="oauth_states")
    op.drop_table("oauth_states")
