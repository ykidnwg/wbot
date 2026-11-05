"""Publishing-provider boundary and Facebook Graph implementation."""

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.providers.meta import MetaConfig


class PublishingError(Exception):
    """A publish failure with a category and whether the outcome is ambiguous."""

    def __init__(
        self,
        category: str,
        message: str,
        *,
        status_code: int | None = None,
        uncertain: bool = False,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.safe_message = message
        self.status_code = status_code
        self.uncertain = uncertain


@dataclass(frozen=True)
class PublishResult:
    external_post_id: str
    published_url: str | None


class Publisher(Protocol):
    platform: str

    async def publish(
        self,
        *,
        external_target_id: str,
        access_token: str,
        caption: str,
        image_data: bytes | None = None,
        image_mime_type: str | None = None,
    ) -> PublishResult: ...


class FacebookPagePublisher:
    platform = "facebook"

    def __init__(self, config: MetaConfig, timeout_seconds: float = 45.0) -> None:
        self.base_url = f"https://graph.facebook.com/{config.graph_api_version}"
        self.timeout_seconds = timeout_seconds

    async def publish(
        self,
        *,
        external_target_id: str,
        access_token: str,
        caption: str,
        image_data: bytes | None = None,
        image_mime_type: str | None = None,
    ) -> PublishResult:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                if image_data is not None:
                    extension = {
                        "image/png": "image.png",
                        "image/jpeg": "image.jpg",
                        "image/webp": "image.webp",
                    }.get(image_mime_type or "", "image.png")
                    response = await client.post(
                        f"{self.base_url}/{external_target_id}/photos",
                        data={"access_token": access_token, "caption": caption},
                        files={"source": (extension, image_data, image_mime_type or "image/png")},
                    )
                else:
                    response = await client.post(
                        f"{self.base_url}/{external_target_id}/feed",
                        data={"access_token": access_token, "message": caption},
                    )
        except httpx.TimeoutException as exc:
            raise PublishingError(
                "network",
                "Facebook timed out before confirming the publish result",
                uncertain=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise PublishingError("network", "Facebook is unreachable") from exc

        if response.status_code >= 400:
            category = _category_for_status(response.status_code)
            raise PublishingError(
                category,
                f"Facebook rejected the post (HTTP {response.status_code})",
                status_code=response.status_code,
                uncertain=response.status_code >= 500,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise PublishingError(
                "unknown", "Facebook returned an invalid response", uncertain=True
            ) from exc
        post_id = payload.get("id") or payload.get("post_id")
        if not isinstance(post_id, str) or not post_id:
            raise PublishingError(
                "unknown", "Facebook did not return a post identifier", uncertain=True
            )
        return PublishResult(
            external_post_id=post_id,
            published_url=_url_for_post(external_target_id, post_id),
        )


def _category_for_status(status_code: int) -> str:
    if status_code in {401}:
        return "auth"
    if status_code in {403}:
        return "permission"
    if status_code == 429:
        return "rate_limit"
    if status_code in {400, 422}:
        return "validation"
    if status_code >= 500:
        return "temporary"
    return "unknown"


def _url_for_post(page_id: str, post_id: str) -> str | None:
    story_id = post_id.split("_", 1)[1] if "_" in post_id else post_id
    if not story_id.isdigit():
        return None
    return f"https://www.facebook.com/{page_id}/posts/{story_id}"
