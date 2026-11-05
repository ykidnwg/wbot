"""Provider selection and status without exposing credentials."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.providers.caption import (
    CaptionProvider,
    MockCaptionProvider,
    OpenAICaptionProvider,
)
from app.providers.image import ImageProvider, MockImageProvider, OpenAIImageProvider
from app.services.setting import get_setting_value

settings = get_settings()


@dataclass(frozen=True)
class ProviderStatus:
    id: str
    label: str
    kind: str
    mode: str
    status: str
    model: str
    api_base: str | None
    message: str | None


async def build_caption_provider(db: AsyncSession) -> CaptionProvider:
    selected = (await get_setting_value(db, "caption_provider")) or "mock"
    if selected != "openai":
        return MockCaptionProvider()
    base_url = (await get_setting_value(db, "openai_api_base")) or settings.openai_api_base
    model = (await get_setting_value(db, "caption_model")) or "gpt-4o-mini"
    return OpenAICaptionProvider(
        api_key=settings.openai_api_key,
        base_url=base_url,
        model=model,
    )


def build_image_provider_sync(
    *, selected: str, base_url: str, model: str
) -> ImageProvider:
    if selected != "openai":
        return MockImageProvider()
    return OpenAIImageProvider(
        api_key=settings.openai_api_key,
        base_url=base_url,
        model=model,
    )


async def build_image_provider(db: AsyncSession) -> ImageProvider:
    selected = (await get_setting_value(db, "image_provider")) or "mock"
    base_url = (await get_setting_value(db, "openai_api_base")) or settings.openai_api_base
    model = (await get_setting_value(db, "image_model")) or "gpt-image-1"
    return build_image_provider_sync(selected=selected, base_url=base_url, model=model)


async def get_provider_statuses(db: AsyncSession) -> list[ProviderStatus]:
    caption_selected = (await get_setting_value(db, "caption_provider")) or "mock"
    image_selected = (await get_setting_value(db, "image_provider")) or "mock"
    caption_model = (await get_setting_value(db, "caption_model")) or "gpt-4o-mini"
    image_model = (await get_setting_value(db, "image_model")) or "gpt-image-1"
    base_url = (await get_setting_value(db, "openai_api_base")) or settings.openai_api_base
    has_key = bool(settings.openai_api_key)

    caption_status = "mock" if caption_selected == "mock" else (
        "configured" if has_key else "NEEDS_CREDENTIALS"
    )
    image_status = "mock" if image_selected == "mock" else (
        "configured" if has_key else "NEEDS_CREDENTIALS"
    )
    return [
        ProviderStatus(
            id="caption",
            label="Caption generation",
            kind="caption",
            mode="mock" if caption_selected == "mock" else "live",
            status=caption_status,
            model=caption_model if caption_selected != "mock" else "template-v1",
            api_base=base_url if caption_selected != "mock" else None,
            message=(
                "Deterministic local provider. Output is labeled as mock."
                if caption_selected == "mock"
                else (None if has_key else "Set OPENAI_API_KEY on the server.")
            ),
        ),
        ProviderStatus(
            id="image",
            label="Image generation",
            kind="image",
            mode="mock" if image_selected == "mock" else "live",
            status=image_status,
            model=image_model if image_selected != "mock" else "solid-png-v1",
            api_base=base_url if image_selected != "mock" else None,
            message=(
                "Deterministic local image provider."
                if image_selected == "mock"
                else (None if has_key else "Set OPENAI_API_KEY on the server.")
            ),
        ),
        ProviderStatus(
            id="facebook",
            label="Facebook Pages",
            kind="publishing",
            mode="live" if _meta_configured() else "unconfigured",
            status="configured" if _meta_configured() else "NEEDS_CREDENTIALS",
            model=f"Graph {settings.meta_graph_api_version}",
            api_base=None,
            message=None if _meta_configured() else "Set Meta app credentials on the server.",
        ),
    ]


def _meta_configured() -> bool:
    return bool(
        settings.meta_app_id
        and settings.meta_app_secret
        and settings.meta_oauth_redirect_uri
        and settings.token_encryption_key
    )
