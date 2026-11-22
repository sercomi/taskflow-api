from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services.user import update_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    try:
        return await update_user(session, current_user, user_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        ) from exc
