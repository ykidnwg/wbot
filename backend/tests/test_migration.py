import os
import tempfile

import alembic.command
import alembic.config
import sqlalchemy


def test_initial_migration_is_repeatable() -> None:
    backend_root = os.path.dirname(os.path.dirname(__file__))
    database_path = os.path.join(tempfile.gettempdir(), "ai_social_migration_contract.db")
    if os.path.exists(database_path):
        os.unlink(database_path)
    config = alembic.config.Config(os.path.join(backend_root, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(backend_root, "alembic"))
    database_url = f"sqlite:///{database_path.replace(os.sep, '/')}"
    config.set_main_option("sqlalchemy.url", database_url)

    alembic.command.upgrade(config, "head")
    alembic.command.upgrade(config, "head")

    migration_engine = sqlalchemy.create_engine(database_url)
    try:
        tables = set(sqlalchemy.inspect(migration_engine).get_table_names())
        expected = {
            "alembic_version",
            "users",
            "sessions",
            "settings",
            "audit_logs",
            "notifications",
            "personas",
            "persona_versions",
            "persona_batches",
            "persona_candidates",
            "generation_jobs",
            "content_items",
            "content_versions",
            "approval_events",
            "media_assets",
            "oauth_states",
            "social_connections",
            "social_targets",
            "persona_assignments",
            "schedules",
            "browser_accounts",
            "browser_profiles",
            "browser_jobs",
            "browser_events",
            "browser_workers",
            "publishing_jobs",
            "publishing_attempts",
            "campaigns",
            "campaign_links",
            "campaign_clicks",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"
    finally:
        migration_engine.dispose()
        os.unlink(database_path)
