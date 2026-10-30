from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Social Automation"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    database_url: str
    database_url_sync: str
    redis_url: str
    backend_cors_origins: str = "http://localhost:3000"
    session_cookie_name: str = "ai_social_session"
    session_cookie_secure: bool = False
    session_ttl_hours: int = Field(default=24, ge=1, le=24 * 30)
    initial_admin_email: str | None = None
    initial_admin_password: str | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def validate_security_configuration(self) -> Settings:
        has_email = bool(self.initial_admin_email)
        has_password = bool(self.initial_admin_password)
        if has_email != has_password:
            raise ValueError("INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be set together")
        if self.app_env in {"staging", "production"} and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true outside development/test")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings.model_validate({})
