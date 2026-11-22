from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock

import pytest
from app.api.v1.endpoints.organizations import router
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.organization import OrganizationRole
from app.models.user import User
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def current_user() -> User:
    return User(
        id=1,
        email="test@example.com",
        username="testuser",
        hashed_password="hashed-password",
        is_active=True,
    )


@pytest.fixture
def client(
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


def test_create_organization_success(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.return_value = None

    async def refresh_organization(organization) -> None:
        organization.id = 1
        organization.is_active = True

    mock_session.refresh.side_effect = refresh_organization

    response = client.post(
        "/api/v1/organizations",
        json={
            "name": "Acme Corporation",
            "description": "Acme organization",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Acme Corporation",
        "slug": "acme-corporation",
        "description": "Acme organization",
        "is_active": True,
    }

    mock_session.scalar.assert_awaited_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()


def test_create_organization_assigns_owner(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.return_value = None

    async def refresh_organization(organization) -> None:
        organization.id = 1
        organization.is_active = True

    mock_session.refresh.side_effect = refresh_organization

    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme Corporation"},
    )

    assert response.status_code == 201

    added_objects = [call.args[0] for call in mock_session.add.call_args_list]

    memberships = [obj for obj in added_objects if hasattr(obj, "role")]

    assert len(memberships) == 1
    assert memberships[0].role == OrganizationRole.OWNER
    assert memberships[0].user is not None
    assert memberships[0].user.id == 1

    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()


def test_create_organization_generates_unique_slug(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.side_effect = [1, None]

    async def refresh_organization(organization) -> None:
        organization.id = 2
        organization.is_active = True

    mock_session.refresh.side_effect = refresh_organization

    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme Corporation"},
    )

    assert response.status_code == 201
    assert response.json()["slug"] == "acme-corporation-2"
    assert mock_session.scalar.await_count == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "A"},
        {"name": "A" * 101},
        {"name": "Valid Organization", "description": "A" * 501},
    ],
)
def test_create_organization_invalid_data(
    client: TestClient,
    mock_session: AsyncMock,
    payload: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/organizations",
        json=payload,
    )

    assert response.status_code == 422
    mock_session.commit.assert_not_awaited()


def test_create_organization_integrity_error(
    client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.return_value = None
    mock_session.commit.side_effect = IntegrityError(
        "INSERT INTO organizations",
        {},
        Exception("Unique constraint violation"),
    )

    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme Corporation"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Could not create organization"

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()
