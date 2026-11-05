"""Provider status contracts; credentials never appear in responses."""

from pydantic import BaseModel


class ProviderStatusResponse(BaseModel):
    id: str
    label: str
    kind: str
    mode: str
    status: str
    model: str
    api_base: str | None = None
    message: str | None = None


class ProviderStatusListResponse(BaseModel):
    items: list[ProviderStatusResponse]
