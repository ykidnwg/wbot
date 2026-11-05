"""Validated media persistence behind an object-storage-shaped interface."""

import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import MediaAsset
from app.providers.caption import ProviderError
from app.providers.image import GeneratedImage, detect_image


@dataclass(frozen=True)
class ValidatedMedia:
    mime_type: str
    size_bytes: int
    width: int
    height: int
    checksum: str


class ObjectStorage:
    """Small S3-compatible boundary with a safe local implementation for development."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes) -> str:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid media storage key")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid media storage key")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid media storage key")
        path.unlink(missing_ok=False)


def validate_image(image: GeneratedImage, *, max_size_bytes: int = 10_000_000) -> ValidatedMedia:
    size = len(image.data)
    if size == 0 or size > max_size_bytes:
        raise ValueError("Image size is outside the allowed range")
    if image.mime_type == "image/png":
        width, height = _read_png_dimensions(image.data)
    else:
        try:
            mime_type, width, height = detect_image(image.data)
        except ProviderError as exc:
            raise ValueError(exc.safe_message) from exc
        if mime_type != image.mime_type:
            raise ValueError("Image MIME type does not match its content")
    if (width, height) != (image.width, image.height) or width < 1 or height < 1:
        raise ValueError("Image dimensions are invalid")
    return ValidatedMedia(
        mime_type=image.mime_type,
        size_bytes=size,
        width=width,
        height=height,
        checksum=hashlib.sha256(image.data).hexdigest(),
    )


def _read_png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Image data is not a valid PNG")
    length = struct.unpack(">I", data[8:12])[0]
    if data[12:16] != b"IHDR" or length != 13 or len(data) < 16 + length + 4:
        raise ValueError("PNG header is invalid")
    if zlib.crc32(data[12 : 16 + length]) & 0xFFFFFFFF != struct.unpack(
        ">I", data[16 + length : 20 + length]
    )[0]:
        raise ValueError("PNG header integrity check failed")
    position = 8
    idat = bytearray()
    saw_iend = False
    while position + 12 <= len(data):
        chunk_length = struct.unpack(">I", data[position : position + 4])[0]
        end = position + 12 + chunk_length
        if end > len(data):
            raise ValueError("PNG chunk is truncated")
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + chunk_length]
        crc = struct.unpack(">I", data[position + 8 + chunk_length : end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise ValueError("PNG integrity check failed")
        if kind == b"IDAT":
            idat.extend(payload)
        if kind == b"IEND":
            saw_iend = True
            break
        position = end
    if not saw_iend or not idat:
        raise ValueError("PNG image data is incomplete")
    try:
        zlib.decompress(idat)
    except zlib.error as exc:
        raise ValueError("PNG image data is corrupted") from exc
    return struct.unpack(">II", data[16:24])


async def create_media_asset(
    db: AsyncSession,
    storage: ObjectStorage,
    owner_id: UUID,
    persona_id: UUID,
    prompt: str,
    image: GeneratedImage,
) -> MediaAsset:
    validated = validate_image(image)
    asset_id = uuid4()
    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[validated.mime_type]
    key = f"{owner_id}/{asset_id}.{extension}"
    storage.put(key, image.data)
    asset = MediaAsset(
        id=asset_id,
        owner_id=owner_id,
        persona_id=persona_id,
        storage_key=key,
        mime_type=validated.mime_type,
        size_bytes=validated.size_bytes,
        width=validated.width,
        height=validated.height,
        checksum=validated.checksum,
        provider=image.provider,
        model=image.model,
        prompt=prompt,
    )
    db.add(asset)
    await db.flush()
    await db.refresh(asset)
    return asset


async def get_media_asset(db: AsyncSession, owner_id: UUID, asset_id: UUID) -> MediaAsset | None:
    return await db.scalar(
        select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.owner_id == owner_id)
    )
