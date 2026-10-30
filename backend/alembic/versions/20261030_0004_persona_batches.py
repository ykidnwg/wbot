"""add resumable persona candidate batches

Revision ID: 20261030_0004
Revises: 20261029_0003
Create Date: 2026-10-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0004"
down_revision: str | Sequence[str] | None = "20261029_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "persona_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('draft', 'completed')", name="ck_persona_batches_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_persona_batches_owner_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_persona_batches"),
    )
    op.create_index("ix_persona_batches_owner_id", "persona_batches", ["owner_id"])

    op.create_table(
        "persona_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("persona_id", sa.Uuid(), nullable=True),
        sa.Column("target_label", sa.String(length=160), nullable=False),
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("age >= 18 AND age <= 120", name="ck_persona_candidates_adult_age"),
        sa.CheckConstraint("status IN ('draft', 'approved', 'rejected')", name="ck_persona_candidates_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_persona_candidates_owner_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["persona_batches.id"], name="fk_persona_candidates_batch_id_persona_batches", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], name="fk_persona_candidates_persona_id_personas", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_persona_candidates"),
    )
    op.create_index("ix_persona_candidates_owner_id", "persona_candidates", ["owner_id"])
    op.create_index("ix_persona_candidates_batch_id", "persona_candidates", ["batch_id"])
    op.create_index("ix_persona_candidates_status", "persona_candidates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_persona_candidates_status", table_name="persona_candidates")
    op.drop_index("ix_persona_candidates_batch_id", table_name="persona_candidates")
    op.drop_index("ix_persona_candidates_owner_id", table_name="persona_candidates")
    op.drop_table("persona_candidates")
    op.drop_index("ix_persona_batches_owner_id", table_name="persona_batches")
    op.drop_table("persona_batches")
