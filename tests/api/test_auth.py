from unittest.mock import AsyncMock, MagicMock, patch

import jwt
from app.core.config import settings
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


def test_register_user_success(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result

    async def refresh_user(user: User) -> None:
        user.id = 1
        user.is_active = True

    mock_session.refresh.side_effect = refresh_user

    response = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "email": "test@example.com",
        "username": "testuser",
        "is_active": True,
    }

    assert "password" not in response.json()
    assert "hashed_password" not in response.json()

    mock_session.add.assert_called_once()

    created_user = mock_session.add.call_args.args[0]

    assert isinstance(created_user, User)
    assert created_user.email == "test@example.com"
    assert created_user.username == "testuser"
    assert created_user.hashed_password != "StrongPassword123!"

    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(created_user)


def test_register_user_duplicate_email(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = User(
        id=1,
        email="test@example.com",
        hashed_password="existing_hash",
    )
    mock_session.execute.return_value = result

    response = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_register_user_invalid_email(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-email",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 422


def test_register_user_short_password(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 422


def test_register_user_integrity_error(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result

    mock_session.commit.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("Unique constraint violation"),
    )

    response = auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"
    mock_session.rollback.assert_awaited_once()


def test_login_success(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    user = User(
        id=1,
        email="test@example.com",
        username="testuser",
        hashed_password="hashed-password",
        is_active=True,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_session.execute.return_value = result

    with patch(
        "app.api.v1.endpoints.auth.verify_password",
        return_value=True,
    ):
        response = auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "StrongPassword123!",
            },
        )

    assert response.status_code == 200

    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data

    payload = jwt.decode(
        data["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == "1"


def test_login_user_not_found(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result

    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_invalid_password(
    auth_client: TestClient,
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

    with patch(
        "app.api.v1.endpoints.auth.verify_password",
        return_value=False,
    ):
        response = auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword123!",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_inactive_user(
    auth_client: TestClient,
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

    with patch(
        "app.api.v1.endpoints.auth.verify_password",
        return_value=True,
    ):
        response = auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "StrongPassword123!",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_invalid_email(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "invalid-email",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 422
    mock_session.execute.assert_not_awaited()


def test_login_missing_password(
    auth_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
        },
    )

    assert response.status_code == 422
    mock_session.execute.assert_not_awaited()


def test_login_rejects_password_longer_than_128_characters(
    auth_client: TestClient,
) -> None:
    response = auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "a" * 129,
        },
    )

    assert response.status_code == 422
