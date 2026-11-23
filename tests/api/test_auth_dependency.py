from unittest.mock import AsyncMock, MagicMock

from app.core.security import create_access_token
from app.models.user import User
from fastapi.testclient import TestClient


def test_get_current_user_success(
    dependency_client: TestClient,
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

    response = dependency_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": 1}
    mock_session.execute.assert_awaited_once()


def test_get_current_user_without_token(
    dependency_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = dependency_client.get("/protected")

    assert response.status_code == 401
    mock_session.execute.assert_not_awaited()


def test_get_current_user_invalid_token(
    dependency_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = dependency_client.get(
        "/protected",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    mock_session.execute.assert_not_awaited()


def test_get_current_user_invalid_subject(
    dependency_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    token = create_access_token(subject="invalid")

    response = dependency_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    mock_session.execute.assert_not_awaited()


def test_get_current_user_not_found(
    dependency_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result

    token = create_access_token(subject="999")

    response = dependency_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    mock_session.execute.assert_awaited_once()


def test_get_current_user_inactive(
    dependency_client: TestClient,
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

    response = dependency_client.get(
        "/protected",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user"
