"""Persistence operations for owner-scoped, resumable persona candidate batches."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona import Persona, PersonaBatch, PersonaCandidate, PersonaVersion
from app.schemas.persona_batch import PersonaBatchCreate
from app.services.persona import approve_persona


async def create_batch(
    db: AsyncSession, owner_id: UUID, payload: PersonaBatchCreate
) -> tuple[PersonaBatch, list[PersonaCandidate]]:
    batch = PersonaBatch(owner_id=owner_id, name=payload.name)
    db.add(batch)
    await db.flush()
    candidates = [
        PersonaCandidate(
            owner_id=owner_id,
            batch_id=batch.id,
            **candidate.model_dump(),
        )
        for candidate in payload.candidates
    ]
    db.add_all(candidates)
    await db.flush()
    await db.refresh(batch)
    return batch, candidates


async def list_batches(
    db: AsyncSession, owner_id: UUID, *, page: int, page_size: int
) -> tuple[list[tuple[PersonaBatch, int]], int]:
    total = (
        await db.scalar(
            select(func.count(PersonaBatch.id)).where(PersonaBatch.owner_id == owner_id)
        )
        or 0
    )
    result = await db.execute(
        select(PersonaBatch, func.count(PersonaCandidate.id))
        .outerjoin(PersonaCandidate, PersonaCandidate.batch_id == PersonaBatch.id)
        .where(PersonaBatch.owner_id == owner_id)
        .group_by(PersonaBatch.id)
        .order_by(PersonaBatch.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.tuples().all()), total


async def get_batch(
    db: AsyncSession, owner_id: UUID, batch_id: UUID
) -> tuple[PersonaBatch, list[PersonaCandidate]] | None:
    batch = await db.scalar(
        select(PersonaBatch)
        .where(PersonaBatch.id == batch_id, PersonaBatch.owner_id == owner_id)
        .with_for_update()
    )
    if batch is None:
        return None
    result = await db.scalars(
        select(PersonaCandidate)
        .where(PersonaCandidate.batch_id == batch_id, PersonaCandidate.owner_id == owner_id)
        .order_by(PersonaCandidate.created_at, PersonaCandidate.id)
    )
    return batch, list(result.all())


async def approve_selected_candidates(
    db: AsyncSession,
    owner_id: UUID,
    batch: PersonaBatch,
    candidate_ids: list[UUID],
) -> list[Persona]:
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("Candidate IDs must not be duplicated")
    result = await db.scalars(
        select(PersonaCandidate)
        .where(
            PersonaCandidate.owner_id == owner_id,
            PersonaCandidate.batch_id == batch.id,
            PersonaCandidate.id.in_(candidate_ids),
        )
        .with_for_update()
    )
    candidates = list(result.all())
    if len(candidates) != len(candidate_ids) or any(c.status != "draft" for c in candidates):
        raise ValueError("All selected candidates must be drafts in this batch")

    approved_personas: list[Persona] = []
    for candidate in candidates:
        persona = Persona(
            owner_id=owner_id,
            name=candidate.name,
            age=candidate.age,
            language=candidate.language,
            personality=candidate.personality,
            target_audience=candidate.target_audience,
            clothing_style=candidate.clothing_style,
            identity_description=candidate.identity_description,
            caption_preferences=candidate.caption_preferences.copy(),
            image_provider=candidate.image_provider,
            image_model=candidate.image_model,
            prompt_version=candidate.prompt_version,
        )
        db.add(persona)
        await db.flush()
        version: PersonaVersion = await approve_persona(db, persona, owner_id)
        await db.refresh(persona)
        candidate.status = "approved"
        candidate.persona_id = version.persona_id
        approved_personas.append(persona)

    remaining = (
        await db.scalar(
            select(func.count(PersonaCandidate.id)).where(
                PersonaCandidate.batch_id == batch.id,
                PersonaCandidate.owner_id == owner_id,
                PersonaCandidate.status == "draft",
            )
        )
        or 0
    )
    if remaining == 0:
        batch.status = "completed"
    await db.flush()
    return approved_personas
