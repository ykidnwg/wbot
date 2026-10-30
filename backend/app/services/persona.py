"""Owner-scoped persona use cases and immutable approval snapshots."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona, PersonaVersion
from app.schemas.persona import PersonaCreate


async def list_personas(
    db: AsyncSession, owner_id: UUID, *, page: int, page_size: int
) -> tuple[list[Persona], int]:
    base = select(Persona).where(Persona.owner_id == owner_id)
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    result = await db.scalars(
        base.order_by(Persona.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(result.all()), total


async def get_persona(db: AsyncSession, owner_id: UUID, persona_id: UUID) -> Persona | None:
    return await db.scalar(
        select(Persona).where(Persona.id == persona_id, Persona.owner_id == owner_id)
    )


async def create_persona(db: AsyncSession, owner_id: UUID, payload: PersonaCreate) -> Persona:
    persona = Persona(owner_id=owner_id, **payload.model_dump())
    db.add(persona)
    await db.flush()
    await db.refresh(persona)
    return persona


async def update_draft(db: AsyncSession, persona: Persona, payload: PersonaCreate) -> Persona:
    if persona.status != "draft":
        raise ValueError("Approved personas are immutable; create a new draft to revise")
    persona.name = payload.name
    persona.age = payload.age
    persona.language = payload.language
    persona.personality = payload.personality
    persona.target_audience = payload.target_audience
    persona.clothing_style = payload.clothing_style
    persona.identity_description = payload.identity_description
    persona.caption_preferences = payload.caption_preferences.copy()
    persona.image_provider = payload.image_provider
    persona.image_model = payload.image_model
    persona.prompt_version = payload.prompt_version
    await db.flush()
    await db.refresh(persona)
    return persona


async def approve_persona(db: AsyncSession, persona: Persona, owner_id: UUID) -> PersonaVersion:
    if persona.status != "draft":
        raise ValueError("Only draft personas can be approved")
    version_no = persona.version_no + 1
    version = PersonaVersion(
        owner_id=owner_id,
        persona_id=persona.id,
        version_no=version_no,
        name=persona.name,
        age=persona.age,
        language=persona.language,
        personality=persona.personality,
        target_audience=persona.target_audience,
        clothing_style=persona.clothing_style,
        identity_description=persona.identity_description,
        caption_preferences=persona.caption_preferences.copy(),
        image_provider=persona.image_provider,
        image_model=persona.image_model,
        prompt_version=persona.prompt_version,
    )
    db.add(version)
    persona.status = "approved"
    persona.version_no = version_no
    await db.flush()
    await db.refresh(version)
    return version


async def list_persona_versions(
    db: AsyncSession, owner_id: UUID, persona_id: UUID
) -> list[PersonaVersion]:
    result = await db.scalars(
        select(PersonaVersion)
        .where(PersonaVersion.owner_id == owner_id, PersonaVersion.persona_id == persona_id)
        .order_by(PersonaVersion.version_no.desc())
    )
    return list(result.all())
