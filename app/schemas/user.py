from typing import ClassVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    username: str | None = Field(default=None, min_length=3, max_length=50)
    password: str = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        from_attributes=True,
    )

    id: int
    email: EmailStr
    username: str | None
    is_active: bool


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserUpdate(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
    )

    username: str = Field(
        min_length=3,
        max_length=50,
    )
