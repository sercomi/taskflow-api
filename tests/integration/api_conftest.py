from collections.abc import AsyncGenerator, Callable, Generator

import pytest
from app.core.database import get_session
from app.core.security import create_access_token
from app.main import create_application
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def api_client(
    db_session: AsyncSession,
) -> Generator[TestClient, None, None]:
    application = create_application()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    application.dependency_overrides[get_session] = override_get_session

    with TestClient(application) as client:
        yield client

    application.dependency_overrides.clear()


@pytest.fixture
def auth_headers() -> Callable[[User], dict[str, str]]:
    def create_headers(user: User) -> dict[str, str]:
        token = create_access_token(subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}

    return create_headers
