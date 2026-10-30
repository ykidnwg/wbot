"""Pydantic schemas."""

from app.schemas.audit_log import AuditLogListResponse, AuditLogResponse
from app.schemas.auth import CurrentUserResponse, LoginRequest
from app.schemas.dashboard import DashboardServices, DashboardSummaryResponse
from app.schemas.notification import (
    NotificationListResponse,
    NotificationMarkRead,
    NotificationResponse,
)
from app.schemas.setting import SettingResponse, SettingsListResponse, SettingUpdate

__all__ = [
    "AuditLogListResponse",
    "AuditLogResponse",
    "CurrentUserResponse",
    "DashboardServices",
    "DashboardSummaryResponse",
    "LoginRequest",
    "NotificationListResponse",
    "NotificationMarkRead",
    "NotificationResponse",
    "SettingResponse",
    "SettingUpdate",
    "SettingsListResponse",
]
