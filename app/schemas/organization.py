from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class OrganizationResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    is_active: bool
