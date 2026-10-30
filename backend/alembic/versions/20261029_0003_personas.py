"""add owner-scoped adult personas and immutable approval versions

Revision ID: 20261029_0003
Revises: 20261026_0002
Create Date: 2026-10-29 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0003"
down_revision: str | Sequence[str] | None = "20261026_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "personas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=80), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=False),
        sa.Column("clothing_style", sa.Text(), nullable=False),
        sa.Column("identity_description", sa.Text(), nullable=False),
        sa.Column("caption_preferences", sa.JSON(), nullable=False),
        sa.Column("image_provider", sa.String(length=120), nullable=True),
        sa.Column("image_model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=False, server_default="persona-v1"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("age >= 18 AND age <= 120", name="ck_personas_adult_age"),
        sa.CheckConstraint("status IN ('draft', 'approved', 'archived')", name="ck_personas_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_personas_owner_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_personas"),
    )
    op.create_index("ix_personas_owner_id", "personas", ["owner_id"])
    op.create_index("ix_personas_status", "personas", ["status"])

    op.create_table(
        "persona_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("persona_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=80), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("target_audience", sa.Text(), nullable=False),
        sa.Column("clothing_style", sa.Text(), nullable=False),
        sa.Column("identity_description", sa.Text(), nullable=False),
        sa.Column("caption_preferences", sa.JSON(), nullable=False),
        sa.Column("image_provider", sa.String(length=120), nullable=True),
        sa.Column("image_model", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("age >= 18 AND age <= 120", name="ck_persona_versions_adult_age"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_persona_versions_owner_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], name="fk_persona_versions_persona_id_personas", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_persona_versions"),
        sa.UniqueConstraint("persona_id", "version_no", name="uq_persona_versions_number"),
    )
    op.create_index("ix_persona_versions_owner_id", "persona_versions", ["owner_id"])
    op.create_index("ix_persona_versions_persona_id", "persona_versions", ["persona_id"])


def downgrade() -> None:
    op.drop_index("ix_persona_versions_persona_id", table_name="persona_versions")
    op.drop_index("ix_persona_versions_owner_id", table_name="persona_versions")
    op.drop_table("persona_versions")
    op.drop_index("ix_personas_status", table_name="personas")
    op.drop_index("ix_personas_owner_id", table_name="personas")
    op.drop_table("personas")
