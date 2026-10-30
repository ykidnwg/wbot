"""Batch and candidate contracts for resumable persona onboarding."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.persona import PersonaPayload, PersonaResponse


class PersonaCandidateInput(PersonaPayload):
    target_label: str = Field(min_length=1, max_length=160)


class PersonaBatchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    candidates: list[PersonaCandidateInput] = Field(min_length=1, max_length=100)


class PersonaBatchSummary(BaseModel):
    id: UUID
    name: str
    status: str
    candidate_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonaCandidateResponse(PersonaPayload):
    id: UUID
    batch_id: UUID
    target_label: str
    status: str
    persona_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonaBatchDetail(PersonaBatchSummary):
    candidates: list[PersonaCandidateResponse]


class PersonaBatchListResponse(BaseModel):
    items: list[PersonaBatchSummary]
    total: int


class PersonaSelectedApproval(BaseModel):
    candidate_ids: list[UUID] = Field(min_length=1, max_length=100)


class PersonaSelectedApprovalResponse(BaseModel):
    approved_count: int
    personas: list[PersonaResponse]
