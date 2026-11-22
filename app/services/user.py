from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


async def get_user_by_email(
    session: AsyncSession,
    email: str,
) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    user_data: UserCreate,
) -> User:
    user = User(
        email=str(user_data.email).lower(),
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def update_user(
    session: AsyncSession,
    user: User,
    user_data: UserUpdate,
) -> User:
    update_data = user_data.model_dump(exclude_unset=True)

    username = update_data.get("username")

    if username is not None:
        result = await session.execute(
            select(User).where(
                User.username == username,
                User.id != user.id,
            )
        )

        existing_user = result.scalar_one_or_none()

        if existing_user is not None:
            raise ValueError("Username already registered")

    if "username" in update_data:
        user.username = update_data["username"]

    await session.commit()
    await session.refresh(user)

    return user
