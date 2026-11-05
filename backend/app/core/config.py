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
    meta_app_id: str | None = None
    meta_app_secret: str | None = Field(default=None, repr=False)
    meta_oauth_redirect_uri: str | None = None
    meta_graph_api_version: str = "v26.0"
    token_encryption_key: str | None = Field(default=None, repr=False)
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_api_base: str = "https://api.openai.com/v1"
    worker_inline: bool = False
    worker_poll_seconds: float = Field(default=15.0, ge=1.0, le=300.0)
    media_storage_root: str = "/tmp/ai-social-media"
    browser_headless: bool = True
    browser_no_sandbox: bool = False
    browser_login_timeout_seconds: float = Field(default=300.0, ge=10.0, le=3600.0)
    browser_worker_poll_seconds: float = Field(default=15.0, ge=1.0, le=300.0)
    browser_facebook_base_url: str = "https://www.facebook.com"
    browser_facebook_publish_enabled: bool = False
    browser_facebook_composer_url: str | None = None
    browser_facebook_authenticated_selector: str = '[aria-label="Your profile"]'
    browser_facebook_caption_selector: str = '[contenteditable="true"][role="textbox"]'
    browser_facebook_submit_selector: str = '[aria-label="Post"]'
    browser_facebook_success_selector: str | None = None
    browser_facebook_media_input_selector: str = 'input[type="file"]'

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
