"""Service layer for system settings."""

import math
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import DEFAULT_SETTINGS, Setting


async def ensure_default_settings(db: AsyncSession) -> None:
    """Insert missing default settings. Idempotent."""
    for key, meta in DEFAULT_SETTINGS.items():
        existing = await db.scalar(select(Setting).where(Setting.key == key))
        if existing is None:
            db.add(
                Setting(
                    key=key,
                    value=meta["value"],
                    value_type=meta["value_type"],
                    description=meta["description"],
                )
            )
    await db.flush()


async def get_all_settings(db: AsyncSession) -> list[Setting]:
    """Return all settings ordered by key."""
    result = await db.scalars(select(Setting).order_by(Setting.key))
    return list(result.all())


async def get_setting_value(db: AsyncSession, key: str) -> str | None:
    """Get a single setting value by key."""
    setting = await db.scalar(select(Setting).where(Setting.key == key))
    return setting.value if setting else None


async def get_setting_bool(db: AsyncSession, key: str) -> bool:
    """Get a boolean setting. Returns False if key not found."""
    value = await get_setting_value(db, key)
    return value is not None and value.lower() in ("true", "1", "yes")


async def get_setting_int(db: AsyncSession, key: str, default: int = 0) -> int:
    """Get an integer setting."""
    value = await get_setting_value(db, key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


async def get_setting_float(db: AsyncSession, key: str, default: float = 0.0) -> float:
    """Get a float setting."""
    value = await get_setting_value(db, key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


async def update_setting(
    db: AsyncSession, key: str, value: str, updated_by: UUID | None = None
) -> Setting | None:
    """Update a setting value. Returns None if key not found."""
    setting = await db.scalar(select(Setting).where(Setting.key == key))
    if setting is None:
        return None
    # Validate value matches declared type
    _validate_value_type(key, value, setting.value_type)
    setting.value = value
    setting.updated_by = updated_by
    await db.flush()
    await db.refresh(setting)
    return setting


def _validate_value_type(key: str, value: str, value_type: str) -> None:
    """Validate settings types and operational bounds before persisting."""
    if value_type == "boolean":
        if value.lower() not in ("true", "false"):
            raise ValueError("Boolean settings must be 'true' or 'false'")
    elif value_type == "integer":
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError("Setting must be a whole number") from exc
        limits = {
            "max_generation_concurrency": (1, 32),
            "max_publishing_concurrency": (1, 32),
            "max_retry_attempts": (0, 10),
            "rate_limit_login_per_minute": (1, 1000),
            "rate_limit_api_per_minute": (1, 10000),
        }
        if key in limits and not limits[key][0] <= parsed <= limits[key][1]:
            low, high = limits[key]
            raise ValueError(f"Value must be between {low} and {high}")
    elif value_type == "float":
        try:
            parsed_float = float(value)
        except ValueError as exc:
            raise ValueError("Setting must be a number") from exc
        if not math.isfinite(parsed_float) or not 0 <= parsed_float <= 1_000_000:
            raise ValueError("Budget must be between 0 and 1000000")
    elif key == "default_timezone":
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("Timezone must be a valid IANA timezone") from exc
