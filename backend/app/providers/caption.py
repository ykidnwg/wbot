"""Caption-provider contracts, mock, and configurable OpenAI-compatible adapter."""

from dataclasses import dataclass, field
from typing import Protocol

import httpx


class ProviderError(Exception):
    """Categorized provider failure with a safe, secret-free message."""

    def __init__(self, category: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.safe_message = message
        self.status_code = status_code


@dataclass(frozen=True)
class CaptionRequest:
    persona_name: str
    language: str
    topic: str
    platform: str = "unassigned"
    personality: str = ""
    target_audience: str = ""
    identity_description: str = ""
    preferences: dict[str, object] = field(default_factory=dict)
    aspect_ratio: str = "square"


class CaptionProvider(Protocol):
    name: str
    model: str
    mode: str

    async def generate(self, request: CaptionRequest) -> str: ...

    def validate_configuration(self) -> bool: ...

    def get_health(self) -> str: ...


class MockCaptionProvider:
    """A deterministic template provider; output is always labeled as mock in metadata."""

    name = "mock"
    model = "template-v1"
    mode = "mock"

    async def generate(self, request: CaptionRequest) -> str:
        if request.language.lower().startswith(("bahasa", "indonesian")):
            return (
                f"{request.topic.strip()} \u2014 momen kecil untuk menikmati hari.\n\n"
                f"\u2014 {request.persona_name}"
            )
        return (
            f"{request.topic.strip()} \u2014 a small moment to enjoy the day.\n\n"
            f"\u2014 {request.persona_name}"
        )

    def validate_configuration(self) -> bool:
        return True

    def get_health(self) -> str:
        return "ok"


class OpenAICaptionProvider:
    """OpenAI-compatible chat-completions adapter.

    The endpoint is configurable so a self-hosted or gateway provider with the same
    documented contract can be used. No request is made unless an API key exists.
    """

    name = "openai"
    mode = "live"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def validate_configuration(self) -> bool:
        return bool(self.api_key and self.model and self.base_url.startswith("https://"))

    def get_health(self) -> str:
        return "ok" if self.validate_configuration() else "NEEDS_CREDENTIALS"

    async def generate(self, request: CaptionRequest) -> str:
        if not self.validate_configuration():
            raise ProviderError("auth", "NEEDS_CREDENTIALS")
        prompt = _caption_prompt(request)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "temperature": 0.8,
                        "max_tokens": 600,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You write social captions for a fictional adult persona. "
                                    "Never claim the persona is a real person. Follow platform "
                                    "policies, avoid explicit sexual content, and do not invent "
                                    "facts, prices, partnerships, or medical claims."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("network", "Caption provider timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network", "Caption provider is unreachable") from exc

        if response.status_code == 429:
            raise ProviderError(
                "rate_limit", "Caption provider rate limit reached", status_code=429
            )
        if response.status_code >= 400:
            category = "auth" if response.status_code in {401, 403} else "unknown"
            raise ProviderError(
                category,
                f"Caption provider rejected the request (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("unknown", "Caption provider returned an invalid response") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("unknown", "Caption provider returned an empty caption")
        return content.strip()


def _caption_prompt(request: CaptionRequest) -> str:
    preferences = request.preferences or {}
    style = preferences.get("style") or "natural, warm, and concise"
    disclosure = preferences.get("disclosure") or "none"
    return (
        f"Persona: {request.persona_name}\n"
        f"Personality: {request.personality or 'not specified'}\n"
        f"Visual identity: {request.identity_description or 'not specified'}\n"
        f"Target audience: {request.target_audience or 'general adult audience'}\n"
        f"Language: {request.language}\n"
        f"Platform: {request.platform}\n"
        f"Topic: {request.topic}\n"
        f"Caption style: {style}\n"
        f"Required disclosure: {disclosure}\n\n"
        "Write one caption of at most 180 words. Include a short call to action and "
        "3-8 relevant hashtags at the end. Do not wrap the response in quotes."
    )
