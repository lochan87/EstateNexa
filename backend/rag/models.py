from typing import Any, Literal

from pydantic import BaseModel, Field


RoleType = Literal["buyer", "agent", "admin"]


class PropertyFilters(BaseModel):
    budget: float | None = Field(default=None, ge=0)
    location: str | None = None
    bedrooms: int | None = Field(default=None, ge=0)
    property_type: str | None = None


class PropertyRetrievalInput(BaseModel):
    query: str = Field(..., min_length=2)
    filters: PropertyFilters = Field(default_factory=PropertyFilters)
    user_role: RoleType


class PropertyResult(BaseModel):
    property_id: str
    location: str | None = None
    price: Any
    bedrooms: int | None = None
    property_type: str | None = None
    highlights: list[str]
    summary: str
