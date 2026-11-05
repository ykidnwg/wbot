"""add browser accounts, profiles, jobs, events, workers, and schedule destination

Revision ID: 20261103_0009
Revises: 20261102_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_0009"
down_revision: str | Sequence[str] | None = "20261102_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "browser_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("handle", sa.String(length=255), nullable=True),
        sa.Column("profile_image_url", sa.String(length=2000), nullable=True),
        sa.Column(
            "status", sa.String(length=30), nullable=False, server_default="NEEDS_LOGIN"
        ),
        sa.Column(
            "session_status", sa.String(length=30), nullable=False, server_default="UNKNOWN"
        ),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_message", sa.Text(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
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
            "platform IN ('facebook', 'instagram', 'threads', 'x')",
            name="ck_browser_accounts_platform",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'NEEDS_LOGIN', 'NEEDS_REAUTHENTICATION', "
            "'DISABLED', 'ERROR')",
            name="ck_browser_accounts_status",
        ),
        sa.CheckConstraint(
            "session_status IN ('UNKNOWN', 'HEALTHY', 'NEEDS_LOGIN', 'EXPIRED', 'ERROR')",
            name="ck_browser_accounts_session_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_browser_accounts_owner_id", "browser_accounts", ["owner_id"])
    op.create_index(
        "ix_browser_accounts_owner_platform", "browser_accounts", ["owner_id", "platform"]
    )

    op.create_table(
        "browser_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("encrypted_storage_state", sa.Text(), nullable=True),
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["browser_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_browser_profiles_account"),
    )
    op.create_index("ix_browser_profiles_owner_id", "browser_profiles", ["owner_id"])
    op.create_index("ix_browser_profiles_account_id", "browser_profiles", ["account_id"])

    with op.batch_alter_table("schedules") as batch_op:
        batch_op.add_column(sa.Column("browser_account_id", sa.Uuid(), nullable=True))
        batch_op.alter_column("social_target_id", existing_type=sa.Uuid(), nullable=True)
        batch_op.create_foreign_key(
            "fk_schedules_browser_account_id_browser_accounts",
            "browser_accounts",
            ["browser_account_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_schedules_browser_account_id", ["browser_account_id"])
        batch_op.create_check_constraint(
            "ck_schedules_one_destination",
            "(social_target_id IS NOT NULL AND browser_account_id IS NULL) "
            "OR (social_target_id IS NULL AND browser_account_id IS NOT NULL)",
        )

    op.create_table(
        "browser_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("content_item_id", sa.Uuid(), nullable=True),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="QUEUED"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_post_id", sa.String(length=255), nullable=True),
        sa.Column("published_url", sa.String(length=2000), nullable=True),
        sa.Column("error_category", sa.String(length=40), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False),
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
            "job_type IN ('PUBLISH', 'CHECK_SESSION', 'LOGIN')",
            name="ck_browser_jobs_type",
        ),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'SUCCESS', 'FAILED', "
            "'NEEDS_USER_ACTION', 'UNKNOWN', 'CANCELLED')",
            name="ck_browser_jobs_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_browser_jobs_attempts"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["browser_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["content_item_id"], ["content_items.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_browser_jobs_owner_idempotency"
        ),
    )
    op.create_index("ix_browser_jobs_owner_id", "browser_jobs", ["owner_id"])
    op.create_index("ix_browser_jobs_account_id", "browser_jobs", ["account_id"])
    op.create_index("ix_browser_jobs_schedule_id", "browser_jobs", ["schedule_id"])
    op.create_index(
        "ix_browser_jobs_content_item_id", "browser_jobs", ["content_item_id"]
    )
    op.create_index("ix_browser_jobs_due", "browser_jobs", ["status", "next_retry_at"])
    op.create_index(
        "ix_browser_jobs_account_status", "browser_jobs", ["account_id", "status"]
    )

    op.create_table(
        "browser_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("browser_job_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "level IN ('INFO', 'WARNING', 'ERROR')", name="ck_browser_events_level"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["browser_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["browser_job_id"], ["browser_jobs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_browser_events_owner_id", "browser_events", ["owner_id"])
    op.create_index("ix_browser_events_account_id", "browser_events", ["account_id"])
    op.create_index(
        "ix_browser_events_browser_job_id", "browser_events", ["browser_job_id"]
    )
    op.create_index(
        "ix_browser_events_job_created", "browser_events", ["browser_job_id", "created_at"]
    )
    op.create_index(
        "ix_browser_events_account_created",
        "browser_events",
        ["account_id", "created_at"],
    )

    op.create_table(
        "browser_workers",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ONLINE"),
        sa.Column("current_job_id", sa.Uuid(), nullable=True),
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
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
            "status IN ('ONLINE', 'IDLE', 'BUSY', 'OFFLINE', 'ERROR')",
            name="ck_browser_workers_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("browser_workers")
    op.drop_index("ix_browser_events_account_created", table_name="browser_events")
    op.drop_index("ix_browser_events_job_created", table_name="browser_events")
    op.drop_index("ix_browser_events_browser_job_id", table_name="browser_events")
    op.drop_index("ix_browser_events_account_id", table_name="browser_events")
    op.drop_index("ix_browser_events_owner_id", table_name="browser_events")
    op.drop_table("browser_events")
    op.drop_index("ix_browser_jobs_account_status", table_name="browser_jobs")
    op.drop_index("ix_browser_jobs_due", table_name="browser_jobs")
    op.drop_index("ix_browser_jobs_content_item_id", table_name="browser_jobs")
    op.drop_index("ix_browser_jobs_schedule_id", table_name="browser_jobs")
    op.drop_index("ix_browser_jobs_account_id", table_name="browser_jobs")
    op.drop_index("ix_browser_jobs_owner_id", table_name="browser_jobs")
    op.drop_table("browser_jobs")

    op.execute("DELETE FROM schedules WHERE browser_account_id IS NOT NULL")
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.drop_constraint("ck_schedules_one_destination", type_="check")
        batch_op.drop_index("ix_schedules_browser_account_id")
        batch_op.drop_constraint(
            "fk_schedules_browser_account_id_browser_accounts", type_="foreignkey"
        )
        batch_op.drop_column("browser_account_id")
        batch_op.alter_column("social_target_id", existing_type=sa.Uuid(), nullable=False)

    op.drop_index("ix_browser_profiles_account_id", table_name="browser_profiles")
    op.drop_index("ix_browser_profiles_owner_id", table_name="browser_profiles")
    op.drop_table("browser_profiles")
    op.drop_index("ix_browser_accounts_owner_platform", table_name="browser_accounts")
    op.drop_index("ix_browser_accounts_owner_id", table_name="browser_accounts")
    op.drop_table("browser_accounts")
