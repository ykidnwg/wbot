"""Image-provider contracts, deterministic mock, and configurable OpenAI-compatible adapter."""

import base64
import struct
import zlib
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.providers.caption import ProviderError

ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "square": (1024, 1024),
    "portrait": (1024, 1536),
    "vertical": (1024, 1536),
    "landscape": (1536, 1024),
}


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    mime_type: str
    width: int
    height: int
    provider: str
    model: str


class ImageProvider(Protocol):
    name: str
    model: str
    mode: str

    def generate_image(self, *, prompt: str, aspect_ratio: str = "square") -> GeneratedImage: ...

    def validate_configuration(self) -> bool: ...

    def get_health(self) -> str: ...


class MockImageProvider:
    """Produces a deterministic valid PNG and never calls an external service."""

    name = "mock"
    model = "solid-png-v1"
    mode = "mock"

    def generate_image(self, *, prompt: str, aspect_ratio: str = "square") -> GeneratedImage:
        color = bytes(
            (
                sum(prompt.encode("utf-8")) % 256,
                len(prompt.encode("utf-8")) % 256,
                180,
            )
        )
        width, height = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["square"])
        data = _png_solid(width, height, color)
        return GeneratedImage(
            data=data,
            mime_type="image/png",
            width=width,
            height=height,
            provider=self.name,
            model=self.model,
        )

    def validate_configuration(self) -> bool:
        return True

    def get_health(self) -> str:
        return "ok"


class OpenAIImageProvider:
    """OpenAI Images API adapter using the documented generations endpoint.

    Only base64 responses are accepted. A remote URL response is rejected rather than
    fetched by the server, which avoids turning a provider response into an SSRF path.
    """

    name = "openai"
    mode = "live"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def validate_configuration(self) -> bool:
        return bool(self.api_key and self.model and self.base_url.startswith("https://"))

    def get_health(self) -> str:
        return "ok" if self.validate_configuration() else "NEEDS_CREDENTIALS"

    def generate_image(self, *, prompt: str, aspect_ratio: str = "square") -> GeneratedImage:
        if not self.validate_configuration():
            raise ProviderError("auth", "NEEDS_CREDENTIALS")
        size = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["square"])
        body = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": f"{size[0]}x{size[1]}",
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("network", "Image provider timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("network", "Image provider is unreachable") from exc

        if response.status_code == 429:
            raise ProviderError("rate_limit", "Image provider rate limit reached", status_code=429)
        if response.status_code >= 400:
            category = "auth" if response.status_code in {401, 403} else "unknown"
            if response.status_code in {400, 422}:
                category = "validation"
            raise ProviderError(
                category,
                f"Image provider rejected the request (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
            first = payload["data"][0]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("unknown", "Image provider returned an invalid response") from exc
        if not isinstance(first, dict) or not isinstance(first.get("b64_json"), str):
            raise ProviderError(
                "unknown",
                "Image provider did not return base64 image data; remote URL fetching is disabled",
            )
        try:
            data = base64.b64decode(first["b64_json"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ProviderError("unknown", "Image provider returned invalid image data") from exc
        mime_type, width, height = detect_image(data)
        return GeneratedImage(
            data=data,
            mime_type=mime_type,
            width=width,
            height=height,
            provider=self.name,
            model=self.model,
        )


def detect_image(data: bytes) -> tuple[str, int, int]:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        width, height = _read_png_dimensions(data)
        return "image/png", width, height
    if data[:3] == b"\xff\xd8\xff":
        width, height = _read_jpeg_dimensions(data)
        return "image/jpeg", width, height
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        width, height = _read_webp_dimensions(data)
        return "image/webp", width, height
    raise ProviderError("validation", "Image provider returned an unsupported image format")


def _read_png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24:
        raise ProviderError("validation", "PNG image is truncated")
    return struct.unpack(">II", data[16:24])


def _read_jpeg_dimensions(data: bytes) -> tuple[int, int]:
    position = 2
    while position + 9 < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        position += 2
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[position : position + 2])[0]
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            height, width = struct.unpack(">HH", data[position + 3 : position + 7])
            return width, height
        position += segment_length
    raise ProviderError("validation", "JPEG dimensions could not be read")


def _read_webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 30:
        raise ProviderError("validation", "WebP image is truncated")
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    if chunk == b"VP8 ":
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    raise ProviderError("validation", "WebP dimensions could not be read")


def _png_solid(width: int, height: int, color: bytes) -> bytes:
    raw = (b"\x00" + color) * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(
        b"IDAT", zlib.compress(raw)
    ) + chunk(b"IEND", b"")
