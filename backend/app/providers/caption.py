"""Caption-provider contract and deterministic mock for local workflow development."""

from typing import Protocol


class CaptionProvider(Protocol):
    name: str
    model: str

    def generate(self, *, persona_name: str, language: str, topic: str) -> str: ...


class MockCaptionProvider:
    """A deterministic template provider; output is always labeled as mock in metadata."""

    name = "mock"
    model = "template-v1"

    def generate(self, *, persona_name: str, language: str, topic: str) -> str:
        if language.lower().startswith("bahasa") or language.lower().startswith("indonesian"):
            return f"{topic.strip()} — momen kecil untuk menikmati hari.\n\n— {persona_name}"
        return f"{topic.strip()} — a small moment to enjoy the day.\n\n— {persona_name}"
