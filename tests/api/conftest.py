from collections.abc import AsyncGenerator, Generator
from typing import Annotated
from unittest.mock import AsyncMock

import pytest
from app.api.v1.endpoints.organizations import router as organizations_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.tasks import router as tasks_router
from app.api.v1.endpoints.users import router as users_router
from app.core.auth import get_current_user
from app.core.database import get_session
from app.main import create_application
from app.models.user import User
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def projects_client(
    mock_session: AsyncMock,
    current_user: User,
) -> Generator[TestClient, None, None]:
    yield from create_test_client(projects_router, mock_session, current_user)


@pytest.fixture
def tasks_client(
    mock_session: AsyncMock,
    current_user: User,
) -> Generator[TestClient, None, None]:
    yield from create_test_client(tasks_router, mock_session, current_user)


@pytest.fixture
def organizations_client(
    mock_session: AsyncMock,
    current_user: User,
) -> Generator[TestClient, None, None]:
    yield from create_test_client(
        organizations_router,
        mock_session,
        current_user,
    )


@pytest.fixture
def users_client(
    mock_session: AsyncMock,
    current_user: User,
) -> Generator[TestClient, None, None]:
    yield from create_test_client(
        users_router,
        mock_session,
        current_user,
    )


@pytest.fixture
def auth_client(
    mock_session: AsyncMock,
) -> Generator[TestClient, None, None]:
    application = create_application()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    application.dependency_overrides[get_session] = override_get_session

    with TestClient(application) as test_client:
        yield test_client

    application.dependency_overrides.clear()


@pytest.fixture
def dependency_client(
    mock_session: AsyncMock,
) -> Generator[TestClient, None, None]:
    application = FastAPI()

    @application.get("/protected")
    async def protected_route(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> dict[str, int]:
        return {"user_id": current_user.id}

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    application.dependency_overrides[get_session] = override_get_session

    with TestClient(application) as test_client:
        yield test_client

    application.dependency_overrides.clear()


def create_test_client(
    router: APIRouter,
    mock_session: AsyncMock,
    current_user: User,
) -> Generator[TestClient, None, None]:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    async def override_get_current_user() -> User:
        return current_user

    application.dependency_overrides[get_session] = override_get_session
    application.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(application) as test_client:
        yield test_client

    application.dependency_overrides.clear()
