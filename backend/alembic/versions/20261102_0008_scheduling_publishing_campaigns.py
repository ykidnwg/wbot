"""add scheduling, publishing, campaign, and media-link tables

Revision ID: 20261102_0008
Revises: 20261101_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0008"
down_revision: str | Sequence[str] | None = "20261101_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("content_items") as batch_op:
        batch_op.add_column(sa.Column("media_asset_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_content_items_media_asset_id_media_assets",
            "media_assets",
            ["media_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_content_items_media_asset_id", ["media_asset_id"])

    with op.batch_alter_table("content_versions") as batch_op:
        batch_op.add_column(sa.Column("media_asset_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_content_versions_media_asset_id_media_assets",
            "media_assets",
            ["media_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_content_versions_media_asset_id", ["media_asset_id"])

    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.Column("social_target_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="scheduled"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'cancelled', 'publishing', 'published', 'failed', "
            "'uncertain')",
            name="ck_schedules_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["social_target_id"], ["social_targets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="uq_schedules_owner_idempotency"),
    )
    op.create_index("ix_schedules_owner_id", "schedules", ["owner_id"])
    op.create_index("ix_schedules_content_item_id", "schedules", ["content_item_id"])
    op.create_index("ix_schedules_social_target_id", "schedules", ["social_target_id"])
    op.create_index("ix_schedules_scheduled_for", "schedules", ["scheduled_for"])
    op.create_index("ix_schedules_due", "schedules", ["status", "scheduled_for"])

    op.create_table(
        "publishing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("content_item_id", sa.Uuid(), nullable=False),
        sa.Column("social_target_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("external_post_id", sa.String(length=255), nullable=True),
        sa.Column("published_url", sa.String(length=2000), nullable=True),
        sa.Column("error_category", sa.String(length=40), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'retry_wait', "
            "'cancelled', 'needs_credentials', 'needs_approval', 'uncertain')",
            name="ck_publishing_jobs_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_publishing_jobs_attempts"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["social_target_id"], ["social_targets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_publishing_jobs_owner_idempotency"
        ),
    )
    op.create_index("ix_publishing_jobs_owner_id", "publishing_jobs", ["owner_id"])
    op.create_index("ix_publishing_jobs_schedule_id", "publishing_jobs", ["schedule_id"])
    op.create_index(
        "ix_publishing_jobs_content_item_id", "publishing_jobs", ["content_item_id"]
    )
    op.create_index(
        "ix_publishing_jobs_social_target_id", "publishing_jobs", ["social_target_id"]
    )
    op.create_index("ix_publishing_jobs_due", "publishing_jobs", ["status", "next_retry_at"])

    op.create_table(
        "publishing_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("publishing_job_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_category", sa.String(length=40), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("external_post_id", sa.String(length=255), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed', 'uncertain', 'rate_limited')",
            name="ck_publishing_attempts_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["publishing_job_id"], ["publishing_jobs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publishing_job_id", "attempt_no", name="uq_publishing_attempts_number"
        ),
    )
    op.create_index("ix_publishing_attempts_owner_id", "publishing_attempts", ["owner_id"])
    op.create_index(
        "ix_publishing_attempts_publishing_job_id",
        "publishing_attempts",
        ["publishing_job_id"],
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("persona_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(length=40), nullable=False, server_default="multi"),
        sa.Column("destination_url", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'ended', 'archived')",
            name="ck_campaigns_status",
        ),
        sa.CheckConstraint(
            "platform IN ('facebook', 'instagram', 'threads', 'x', 'multi')",
            name="ck_campaigns_platform",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_owner_id", "campaigns", ["owner_id"])
    op.create_index("ix_campaigns_persona_id", "campaigns", ["persona_id"])

    op.create_table(
        "campaign_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("affiliate_url", sa.String(length=2000), nullable=False),
        sa.Column("tracking_id", sa.String(length=64), nullable=False),
        sa.Column("utm_source", sa.String(length=160), nullable=True),
        sa.Column("utm_medium", sa.String(length=160), nullable=True),
        sa.Column("utm_campaign", sa.String(length=160), nullable=True),
        sa.Column("utm_term", sa.String(length=160), nullable=True),
        sa.Column("utm_content", sa.String(length=160), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tracking_id", name="uq_campaign_links_tracking"),
    )
    op.create_index("ix_campaign_links_owner_id", "campaign_links", ["owner_id"])
    op.create_index("ix_campaign_links_campaign_id", "campaign_links", ["campaign_id"])

    op.create_table(
        "campaign_clicks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_link_id", sa.Uuid(), nullable=False),
        sa.Column(
            "clicked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("referrer_host", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["campaign_link_id"], ["campaign_links.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_clicks_owner_id", "campaign_clicks", ["owner_id"])
    op.create_index(
        "ix_campaign_clicks_campaign_link_id", "campaign_clicks", ["campaign_link_id"]
    )
    op.create_index("ix_campaign_clicks_clicked_at", "campaign_clicks", ["clicked_at"])
    op.create_index(
        "ix_campaign_clicks_link_time", "campaign_clicks", ["campaign_link_id", "clicked_at"]
    )


def downgrade() -> None:
    op.drop_table("campaign_clicks")
    op.drop_table("campaign_links")
    op.drop_table("campaigns")
    op.drop_table("publishing_attempts")
    op.drop_table("publishing_jobs")
    op.drop_table("schedules")
    with op.batch_alter_table("content_versions") as batch_op:
        batch_op.drop_index("ix_content_versions_media_asset_id")
        batch_op.drop_constraint(
            "fk_content_versions_media_asset_id_media_assets", type_="foreignkey"
        )
        batch_op.drop_column("media_asset_id")
    with op.batch_alter_table("content_items") as batch_op:
        batch_op.drop_index("ix_content_items_media_asset_id")
        batch_op.drop_constraint(
            "fk_content_items_media_asset_id_media_assets", type_="foreignkey"
        )
        batch_op.drop_column("media_asset_id")
