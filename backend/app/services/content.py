"""Content factory use cases with owner checks and explicit mock-provider metadata."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    ApprovalEvent,
    ContentItem,
    ContentVersion,
    GenerationJob,
    MediaAsset,
)
from app.models.persona import Persona
from app.providers.caption import CaptionProvider, CaptionRequest, MockCaptionProvider
from app.schemas.content import CaptionGenerationRequest


async def list_content(
    db: AsyncSession, owner_id: UUID, *, page: int, page_size: int
) -> tuple[list[ContentItem], int]:
    base = select(ContentItem).where(ContentItem.owner_id == owner_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    result = await db.scalars(
        base.order_by(ContentItem.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(result.all()), total


async def generate_caption_draft(
    db: AsyncSession,
    owner_id: UUID,
    payload: CaptionGenerationRequest,
    provider: CaptionProvider | None = None,
) -> ContentItem:
    persona = await db.scalar(
        select(Persona).where(
            Persona.id == payload.persona_id,
            Persona.owner_id == owner_id,
            Persona.status == "approved",
        )
    )
    if persona is None:
        raise ValueError("Only an owned, approved persona can generate a content draft")

    caption_provider = provider or MockCaptionProvider()
    caption = await caption_provider.generate(
        CaptionRequest(
            persona_name=persona.name,
            language=persona.language,
            topic=payload.topic,
            platform=payload.platform,
            personality=persona.personality,
            target_audience=persona.target_audience,
            identity_description=persona.identity_description,
            preferences=persona.caption_preferences,
            aspect_ratio=payload.aspect_ratio,
        )
    )
    job = GenerationJob(
        owner_id=owner_id,
        persona_id=persona.id,
        status="succeeded",
        provider=caption_provider.name,
        model=caption_provider.model,
        prompt_version=persona.prompt_version,
        topic=payload.topic,
        attempt_count=1,
    )
    db.add(job)
    await db.flush()
    item = ContentItem(
        owner_id=owner_id,
        persona_id=persona.id,
        generation_job_id=job.id,
        platform=payload.platform,
        topic=payload.topic,
        caption=caption,
        provider=f"{caption_provider.name}/{caption_provider.model}",
        status="draft",
        version_no=1,
    )
    db.add(item)
    await db.flush()
    db.add(
        ContentVersion(
            owner_id=owner_id,
            content_item_id=item.id,
            version_no=1,
            caption=caption,
            media_asset_id=None,
            provider=item.provider,
        )
    )
    await db.flush()
    await db.refresh(item)
    return item


async def decide_content(
    db: AsyncSession,
    owner_id: UUID,
    content_id: UUID,
    decision: str,
    reason: str | None,
) -> ContentItem | None:
    item = await db.scalar(
        select(ContentItem)
        .where(ContentItem.id == content_id, ContentItem.owner_id == owner_id)
        .with_for_update()
    )
    if item is None:
        return None
    if item.status != "draft":
        raise ValueError("Only draft content can be approved or rejected")
    version = await db.scalar(
        select(ContentVersion).where(
            ContentVersion.content_item_id == item.id,
            ContentVersion.owner_id == owner_id,
            ContentVersion.version_no == item.version_no,
        )
    )
    if version is None:
        raise ValueError("Current content version is unavailable")
    db.add(
        ApprovalEvent(
            owner_id=owner_id,
            content_item_id=item.id,
            content_version_id=version.id,
            decision=decision,
            reason=reason,
        )
    )
    item.status = decision
    await db.flush()
    await db.refresh(item)
    return item


async def update_content_caption(
    db: AsyncSession, owner_id: UUID, content_id: UUID, caption: str
) -> ContentItem | None:
    """Create a new immutable caption version and require a fresh approval."""
    item = await db.scalar(
        select(ContentItem)
        .where(ContentItem.id == content_id, ContentItem.owner_id == owner_id)
        .with_for_update()
    )
    if item is None:
        return None
    if item.status not in {"draft", "approved", "rejected"}:
        raise ValueError("Only draft, approved, or rejected content can be edited")
    if item.caption == caption:
        raise ValueError("Caption has not changed")
    item.version_no += 1
    item.caption = caption
    item.status = "draft"
    db.add(
        ContentVersion(
            owner_id=owner_id,
            content_item_id=item.id,
            version_no=item.version_no,
            caption=caption,
            media_asset_id=item.media_asset_id,
            provider=item.provider,
        )
    )
    await db.flush()
    await db.refresh(item)
    return item


async def list_content_versions(
    db: AsyncSession, owner_id: UUID, content_id: UUID
) -> list[ContentVersion]:
    result = await db.scalars(
        select(ContentVersion)
        .where(ContentVersion.content_item_id == content_id, ContentVersion.owner_id == owner_id)
        .order_by(ContentVersion.version_no.desc())
    )
    return list(result.all())

async def attach_media(
    db: AsyncSession, owner_id: UUID, content_id: UUID, media_asset_id: UUID | None
) -> ContentItem | None:
    item = await db.scalar(
        select(ContentItem)
        .where(ContentItem.id == content_id, ContentItem.owner_id == owner_id)
        .with_for_update()
    )
    if item is None:
        return None
    if item.status not in {"draft", "approved", "rejected"}:
        raise ValueError("Media can only be changed before scheduling")
    if media_asset_id is not None:
        asset = await db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == media_asset_id,
                MediaAsset.owner_id == owner_id,
            )
        )
        if asset is None:
            raise ValueError("Media asset is not an owned, ready image")
    if item.media_asset_id == media_asset_id:
        return item
    item.version_no += 1
    item.media_asset_id = media_asset_id
    item.status = "draft"
    db.add(
        ContentVersion(
            owner_id=owner_id,
            content_item_id=item.id,
            version_no=item.version_no,
            caption=item.caption,
            media_asset_id=item.media_asset_id,
            provider=item.provider,
        )
    )
    await db.flush()
    await db.refresh(item)
    return item