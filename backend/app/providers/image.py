"""Image-provider contracts and deterministic local implementation."""

from dataclasses import dataclass
from typing import Protocol


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

    def generate_image(self, *, prompt: str) -> GeneratedImage: ...

    def validate_configuration(self) -> bool: ...

    def get_health(self) -> str: ...


class MockImageProvider:
    """Produces a deterministic valid PNG and never calls an external service."""

    name = "mock"
    model = "solid-png-v1"

    def generate_image(self, *, prompt: str) -> GeneratedImage:
        color = bytes(
            (
                sum(prompt.encode("utf-8")) % 256,
                len(prompt.encode("utf-8")) % 256,
                180,
            )
        )
        data = _png_1x1(color)
        return GeneratedImage(
            data=data,
            mime_type="image/png",
            width=1,
            height=1,
            provider=self.name,
            model=self.model,
        )

    def validate_configuration(self) -> bool:
        return True

    def get_health(self) -> str:
        return "ok"


def _png_1x1(color: bytes) -> bytes:
    import struct
    import zlib

    raw = b"\x00" + color
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)

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
