from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints import organizations as organizations_endpoint
from app.models.organization import Organization, OrganizationRole
from app.models.user import User
from app.services.exceptions import (
    DuplicateOrganizationMemberError,
    MemberNotFoundError,
    OrganizationNotFoundError,
    OrganizationOwnerError,
    SelfRemovalError,
    UserNotFoundError,
)
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


def test_create_organization_success(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.return_value = None

    async def refresh_organization(organization: Organization) -> None:
        organization.id = 1
        organization.is_active = True

    mock_session.refresh.side_effect = refresh_organization

    response = organizations_client.post(
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
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.return_value = None

    async def refresh_organization(organization: Organization) -> None:
        organization.id = 1
        organization.is_active = True

    mock_session.refresh.side_effect = refresh_organization

    response = organizations_client.post(
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
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.side_effect = [1, None]

    async def refresh_organization(organization: Organization) -> None:
        organization.id = 2
        organization.is_active = True

    mock_session.refresh.side_effect = refresh_organization

    response = organizations_client.post(
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
    organizations_client: TestClient,
    mock_session: AsyncMock,
    payload: dict[str, str],
) -> None:
    response = organizations_client.post(
        "/api/v1/organizations",
        json=payload,
    )

    assert response.status_code == 422
    mock_session.commit.assert_not_awaited()


def test_create_organization_integrity_error(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.return_value = None
    mock_session.commit.side_effect = IntegrityError(
        "INSERT INTO organizations",
        {},
        Exception("Unique constraint violation"),
    )

    response = organizations_client.post(
        "/api/v1/organizations",
        json={"name": "Acme Corporation"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Could not create organization"

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()


def test_list_organizations_success(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    organizations = [
        Organization(
            id=1,
            name="Acme Corporation",
            slug="acme-corporation",
            description="Acme organization",
            is_active=True,
        ),
        Organization(
            id=2,
            name="Beta Corporation",
            slug="beta-corporation",
            description=None,
            is_active=True,
        ),
    ]

    mock_result = MagicMock()
    mock_result.all.return_value = organizations
    mock_session.scalars.return_value = mock_result

    response = organizations_client.get("/api/v1/organizations")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["name"] == "Acme Corporation"
    assert response.json()[1]["name"] == "Beta Corporation"

    mock_session.scalars.assert_awaited_once()


def test_list_organizations_empty(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.scalars.return_value = mock_result

    response = organizations_client.get("/api/v1/organizations")

    assert response.status_code == 200
    assert response.json() == []

    mock_session.scalars.assert_awaited_once()


def test_list_organizations_excludes_inactive(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    organizations = [
        Organization(
            id=1,
            name="Acme Corporation",
            slug="acme-corporation",
            description=None,
            is_active=True,
        ),
    ]

    mock_result = MagicMock()
    mock_result.all.return_value = organizations
    mock_session.scalars.return_value = mock_result

    response = organizations_client.get("/api/v1/organizations")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["is_active"] is True


def test_get_organization_success(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    organization = Organization(
        id=1,
        name="Acme Corporation",
        slug="acme-corporation",
        description="Acme organization",
        is_active=True,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = organization
    mock_session.execute.return_value = mock_result

    response = organizations_client.get("/api/v1/organizations/1")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "name": "Acme Corporation",
        "slug": "acme-corporation",
        "description": "Acme organization",
        "is_active": True,
    }

    mock_session.execute.assert_awaited_once()


def test_get_organization_not_found(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    response = organizations_client.get("/api/v1/organizations/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"


def test_get_organization_not_member(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    response = organizations_client.get("/api/v1/organizations/2")

    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"


def test_get_organization_inactive(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    response = organizations_client.get("/api/v1/organizations/3")

    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"


def test_list_organization_members_success(
    organizations_client: TestClient,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    members = [
        SimpleNamespace(
            user=current_user,
            role=OrganizationRole.OWNER,
        ),
    ]

    service = AsyncMock(return_value=members)
    monkeypatch.setattr(
        organizations_endpoint,
        "get_organization_members",
        service,
    )

    response = organizations_client.get("/api/v1/organizations/1/members")

    assert response.status_code == 200
    assert response.json() == [
        {
            "user_id": 1,
            "email": "test@example.com",
            "username": "testuser",
            "role": "owner",
        }
    ]


def test_list_organization_members_not_found(
    organizations_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=OrganizationNotFoundError("Organization not found"))
    monkeypatch.setattr(
        organizations_endpoint,
        "get_organization_members",
        service,
    )

    response = organizations_client.get("/api/v1/organizations/999/members")

    assert response.status_code == 404


def test_add_organization_member_success(
    organizations_client: TestClient,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = SimpleNamespace(
        user=current_user,
        role=OrganizationRole.MEMBER,
    )

    service = AsyncMock(return_value=membership)
    monkeypatch.setattr(
        organizations_endpoint,
        "add_organization_member",
        service,
    )

    response = organizations_client.post(
        "/api/v1/organizations/1/members",
        json={"email": "test@example.com"},
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == 1
    assert response.json()["role"] == "member"


@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [
        (OrganizationNotFoundError("Organization not found"), 404),
        (UserNotFoundError("User not found"), 404),
        (PermissionError("Insufficient permissions"), 403),
        (DuplicateOrganizationMemberError("User is already a member"), 409),
    ],
)
def test_add_organization_member_errors(
    organizations_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    expected_status: int,
) -> None:
    service = AsyncMock(side_effect=exception)
    monkeypatch.setattr(
        organizations_endpoint,
        "add_organization_member",
        service,
    )

    response = organizations_client.post(
        "/api/v1/organizations/1/members",
        json={"email": "newuser@example.com"},
    )

    assert response.status_code == expected_status


def test_update_organization_member_role_success(
    organizations_client: TestClient,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = SimpleNamespace(
        user=current_user,
        role=OrganizationRole.ADMIN,
    )

    service = AsyncMock(return_value=membership)
    monkeypatch.setattr(
        organizations_endpoint,
        "update_organization_member_role",
        service,
    )

    response = organizations_client.patch(
        "/api/v1/organizations/1/members/2",
        json={"role": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    service.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [
        (OrganizationNotFoundError("Organization not found"), 404),
        (MemberNotFoundError("Member not found"), 404),
        (PermissionError("Only the owner can update member roles"), 403),
        (OrganizationOwnerError("Cannot change the owner's role"), 409),
    ],
)
def test_update_organization_member_role_errors(
    organizations_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    expected_status: int,
) -> None:
    service = AsyncMock(side_effect=exception)
    monkeypatch.setattr(
        organizations_endpoint,
        "update_organization_member_role",
        service,
    )

    response = organizations_client.patch(
        "/api/v1/organizations/1/members/2",
        json={"role": "member"},
    )

    assert response.status_code == expected_status


def test_update_organization_member_role_rejects_owner(
    organizations_client: TestClient,
    mock_session: AsyncMock,
) -> None:
    response = organizations_client.patch(
        "/api/v1/organizations/1/members/2",
        json={"role": "owner"},
    )

    assert response.status_code == 422
    mock_session.commit.assert_not_awaited()


def test_remove_organization_member_success(
    organizations_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=None)
    monkeypatch.setattr(
        organizations_endpoint,
        "remove_organization_member",
        service,
    )

    response = organizations_client.delete("/api/v1/organizations/1/members/2")

    assert response.status_code == 204
    assert response.content == b""

    service.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [
        (OrganizationNotFoundError("Organization not found"), 404),
        (MemberNotFoundError("Member not found"), 404),
        (PermissionError("Insufficient permissions"), 403),
        (SelfRemovalError("Cannot remove yourself"), 409),
        (OrganizationOwnerError("Cannot remove the organization owner"), 409),
    ],
)
def test_remove_organization_member_errors(
    organizations_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
    expected_status: int,
) -> None:
    service = AsyncMock(side_effect=exception)
    monkeypatch.setattr(
        organizations_endpoint,
        "remove_organization_member",
        service,
    )

    response = organizations_client.delete("/api/v1/organizations/1/members/2")

    assert response.status_code == expected_status
