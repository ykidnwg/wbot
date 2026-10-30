"""add caption-generation content factory and approval history

Revision ID: 20261030_0005
Revises: 20261030_0004
Create Date: 2026-10-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0005"
down_revision: str | Sequence[str] | None = "20261030_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("persona_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False, server_default="caption"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="succeeded"),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("safe_error_message", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'retry_wait', 'failed', 'cancelled', 'blocked')", name="ck_generation_jobs_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_generation_jobs_attempt_count"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_generation_jobs_owner_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], name="fk_generation_jobs_persona_id_personas", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_generation_jobs"),
    )
    op.create_index("ix_generation_jobs_owner_id", "generation_jobs", ["owner_id"])
    op.create_index("ix_generation_jobs_persona_id", "generation_jobs", ["persona_id"])

    op.create_table(
        "content_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("persona_id", sa.Uuid(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False, server_default="unassigned"),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("status IN ('draft', 'generated', 'pending_approval', 'approved', 'rejected', 'scheduled', 'publishing', 'published', 'failed', 'cancelled', 'uncertain')", name="ck_content_items_status"),
        sa.CheckConstraint("platform IN ('facebook', 'instagram', 'threads', 'x', 'unassigned')", name="ck_content_items_platform"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_content_items_owner_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], name="fk_content_items_persona_id_personas", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generation_job_id"], ["generation_jobs.id"], name="fk_content_items_generation_job_id_generation_jobs", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_content_items"),
        sa.UniqueConstraint("generation_job_id", name="uq_content_items_generation_job_id"),
    )
    op.create_index("ix_content_items_owner_id", "content_items", ["owner_id"])
    op.create_index("ix_content_items_persona_id", "content_items", ["persona_id"])
    op.create_index("ix_content_items_status", "content_items", ["status"])

    op.create_table(
        "content_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_content_versions_owner_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], name="fk_content_versions_content_item_id_content_items", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_content_versions"),
        sa.UniqueConstraint("content_item_id", "version_no", name="uq_content_versions_number"),
    )
    op.create_index("ix_content_versions_owner_id", "content_versions", ["owner_id"])
    op.create_index("ix_content_versions_content_item_id", "content_versions", ["content_item_id"])

    op.create_table(
        "approval_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.Column("content_version_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=12), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("decision IN ('approved', 'rejected')", name="ck_approval_events_decision"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_approval_events_owner_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], name="fk_approval_events_content_item_id_content_items", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_version_id"], ["content_versions.id"], name="fk_approval_events_content_version_id_content_versions", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_approval_events"),
    )
    op.create_index("ix_approval_events_owner_id", "approval_events", ["owner_id"])
    op.create_index("ix_approval_events_content_item_id", "approval_events", ["content_item_id"])


def downgrade() -> None:
    op.drop_index("ix_approval_events_content_item_id", table_name="approval_events")
    op.drop_index("ix_approval_events_owner_id", table_name="approval_events")
    op.drop_table("approval_events")
    op.drop_index("ix_content_versions_content_item_id", table_name="content_versions")
    op.drop_index("ix_content_versions_owner_id", table_name="content_versions")
    op.drop_table("content_versions")
    op.drop_index("ix_content_items_status", table_name="content_items")
    op.drop_index("ix_content_items_persona_id", table_name="content_items")
    op.drop_index("ix_content_items_owner_id", table_name="content_items")
    op.drop_table("content_items")
    op.drop_index("ix_generation_jobs_persona_id", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_owner_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")
