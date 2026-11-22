from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.organization import OrganizationRole


class OrganizationMemberCreate(BaseModel):
    email: EmailStr


class OrganizationMemberUpdate(BaseModel):
    role: Literal[
        OrganizationRole.ADMIN,
        OrganizationRole.MEMBER,
    ]


class OrganizationMemberResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    user_id: int
    email: EmailStr
    username: str | None
    role: OrganizationRole
