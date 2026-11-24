from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import (
    create_access_token,
    verify_password,
)
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.user import create_user, get_user_by_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> UserResponse:
    email = str(user_data.email).lower()

    existing_user = await get_user_by_email(session, email)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    try:
        user = await create_user(session, user_data)
    except IntegrityError as exc:
        await session.rollback()

        constraint_name = _get_constraint_name(exc)

        if constraint_name == "ix_users_email":
            detail = "Email already registered"
        elif constraint_name == "users_username_key":
            detail = "Username already registered"
        else:
            raise

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TokenResponse:
    email = str(credentials.email).lower()

    user = await get_user_by_email(session, email)

    if user is None or not verify_password(
        credentials.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=str(user.id))

    return TokenResponse(access_token=access_token)


def _get_constraint_name(exc: IntegrityError) -> str | None:
    error: BaseException | None = exc.orig

    while error is not None:
        constraint_name: object = getattr(error, "constraint_name", None)

        if isinstance(constraint_name, str):
            return constraint_name

        diag: object = getattr(error, "diag", None)

        if diag is not None:
            diag_constraint_name: object = getattr(
                diag,
                "constraint_name",
                None,
            )

            if isinstance(diag_constraint_name, str):
                return diag_constraint_name

        error = error.__cause__ or error.__context__

    return None
