"""Settings API routes."""

from fastapi import APIRouter, HTTPException, Request, status

from app.api.dependencies import CurrentUser, DbSession
from app.schemas.setting import SettingResponse, SettingsListResponse, SettingUpdate
from app.services.audit_log import write_audit_log_from_request
from app.services.setting import get_all_settings, update_setting

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsListResponse)
async def list_settings(_current_user: CurrentUser, db_session: DbSession) -> SettingsListResponse:
    """List all system settings."""
    settings = await get_all_settings(db_session)
    return SettingsListResponse(settings=[SettingResponse.model_validate(s) for s in settings])


@router.put("/{key}", response_model=SettingResponse)
async def update_setting_value(
    key: str,
    body: SettingUpdate,
    current_user: CurrentUser,
    db_session: DbSession,
    request: Request,
) -> SettingResponse:
    """Update a setting value."""
    try:
        setting = await update_setting(db_session, key, body.value, updated_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if setting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    await write_audit_log_from_request(
        db_session,
        request,
        action="setting_updated",
        entity_type="setting",
        entity_id=key,
        details={"new_value": body.value},
        actor_id=current_user.id,
        actor_email=current_user.email,
    )
    await db_session.commit()
    return SettingResponse.model_validate(setting)
