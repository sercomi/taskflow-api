from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.security import create_access_token
from app.models.user import User
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def client(
    mock_session: AsyncMock,
) -> Generator[TestClient, None, None]:
    application = FastAPI()

    @application.get("/protected")
    async def protected(
        current_user: User = Depends(get_current_user),  # noqa: B008
    ) -> dict[str, int]:
        return {"user_id": current_user.id}

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session

    application.dependency_overrides[get_session] = override_get_session

    with TestClient(application) as test_client:
        yield test_client

    application.dependency_overrides.clear()


def test_get_current_user_success(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    user = User(
        id=1,
        email="test@example.com",
        hashed_password="hashed-password",
        is_active=True,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_session.execute.return_value = result

    token = create_access_token(subject="1")

    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": 1}
    mock_session.execute.assert_awaited_once()


def test_get_current_user_without_token(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = client.get("/protected")

    assert response.status_code == 401
    mock_session.execute.assert_not_awaited()


def test_get_current_user_invalid_token(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = client.get(
        "/protected",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    mock_session.execute.assert_not_awaited()


def test_get_current_user_invalid_subject(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    token = create_access_token(subject="invalid")

    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    mock_session.execute.assert_not_awaited()


def test_get_current_user_not_found(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result

    token = create_access_token(subject="999")

    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    mock_session.execute.assert_awaited_once()


def test_get_current_user_inactive(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    user = User(
        id=1,
        email="test@example.com",
        hashed_password="hashed-password",
        is_active=False,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_session.execute.return_value = result

    token = create_access_token(subject="1")

    response = client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user"
