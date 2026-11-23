from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def current_user() -> User:
    return User(
        id=1,
        email="test@example.com",
        username="testuser",
        hashed_password="hashed-password",
        is_active=True,
    )


def test_update_profile_success(
    users_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    async def execute_query(*args: Any, **kwargs: Any) -> MagicMock:
        return result

    async def refresh_user(user: User) -> None:
        assert user is current_user

    mock_session.execute.side_effect = execute_query
    mock_session.refresh.side_effect = refresh_user

    response = users_client.patch(
        "/api/v1/users/me",
        json={"username": "newusername"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "email": "test@example.com",
        "username": "newusername",
        "is_active": True,
    }

    assert current_user.username == "newusername"
    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(current_user)


def test_update_profile_username_null(
    users_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = users_client.patch(
        "/api/v1/users/me",
        json={"username": None},
    )

    assert response.status_code == 422
    mock_session.commit.assert_not_awaited()


def test_update_profile_username_empty(
    users_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = users_client.patch(
        "/api/v1/users/me",
        json={"username": ""},
    )

    assert response.status_code == 422
    mock_session.commit.assert_not_awaited()


def test_update_profile_username_too_short(
    users_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = users_client.patch(
        "/api/v1/users/me",
        json={"username": "ab"},
    )

    assert response.status_code == 422
    mock_session.commit.assert_not_awaited()


def test_update_profile_username_too_long(
    users_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = users_client.patch(
        "/api/v1/users/me",
        json={"username": "a" * 51},
    )

    assert response.status_code == 422
    mock_session.commit.assert_not_awaited()


def test_update_profile_duplicate_username(
    users_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = User(
        id=2,
        email="other@example.com",
        username="existinguser",
        hashed_password="hashed-password",
        is_active=True,
    )
    mock_session.execute.return_value = result

    response = users_client.patch(
        "/api/v1/users/me",
        json={"username": "existinguser"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already registered"
    mock_session.commit.assert_not_awaited()


def test_update_profile_integrity_error(
    users_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result

    mock_session.commit.side_effect = IntegrityError(
        "UPDATE users",
        {},
        Exception("Unique constraint violation"),
    )

    response = users_client.patch(
        "/api/v1/users/me",
        json={"username": "existinguser"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already registered"

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()


def test_update_profile_does_not_allow_sensitive_fields(
    users_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
) -> None:
    response = users_client.patch(
        "/api/v1/users/me",
        json={
            "username": "newusername",
            "is_active": False,
            "email": "other@example.com",
        },
    )

    assert response.status_code == 422
    assert current_user.username == "testuser"
    assert current_user.email == "test@example.com"
    assert current_user.is_active is True

    mock_session.commit.assert_not_awaited()
