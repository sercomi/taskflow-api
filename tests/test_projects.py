from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints import projects as projects_endpoint
from app.api.v1.endpoints.projects import router
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.organization import OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services import project as project_service
from app.services.project import generate_slug, generate_unique_project_slug
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def current_user() -> User:
    return User(
        id=1,
        email="owner@example.com",
        username="owner",
        hashed_password="hashed-password",
        is_active=True,
    )


@pytest.fixture
def owner_membership(current_user: User) -> OrganizationMember:
    return OrganizationMember(
        organization_id=1,
        user_id=current_user.id,
        user=current_user,
        role=OrganizationRole.OWNER,
    )


@pytest.fixture
def sample_project() -> Project:
    return Project(
        id=1,
        organization_id=1,
        name="Backend API",
        slug="backend-api",
        description="Backend project",
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


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Backend API", "backend-api"),
        ("Gestión de tareas", "gestion-de-tareas"),
        ("Project   Alpha", "project-alpha"),
        ("Project@Alpha!", "project-alpha"),
        ("---Project---", "project"),
        ("東京", ""),
    ],
)
def test_generate_slug(name: str, expected: str) -> None:
    assert generate_slug(name) == expected


@pytest.mark.asyncio
async def test_generate_unique_project_slug_returns_base_slug(
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.return_value = None

    result = await generate_unique_project_slug(
        session=mock_session,
        organization_id=1,
        name="Backend API",
    )

    assert result == "backend-api"
    mock_session.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_unique_project_slug_adds_suffix(
    mock_session: AsyncMock,
) -> None:
    mock_session.scalar.side_effect = [1, None]

    result = await generate_unique_project_slug(
        session=mock_session,
        organization_id=1,
        name="Backend API",
    )

    assert result == "backend-api-2"
    assert mock_session.scalar.await_count == 2


@pytest.mark.asyncio
async def test_create_project_success(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    monkeypatch.setattr(
        project_service,
        "generate_unique_project_slug",
        AsyncMock(return_value="backend-api"),
    )

    result = await project_service.create_project(
        session=mock_session,
        organization_id=1,
        project_data=ProjectCreate(name="Backend API"),
        current_user=current_user,
    )

    assert result.name == "Backend API"
    assert result.slug == "backend-api"
    assert result.organization_id == 1
    assert result.description is None

    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_create_project_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=None),
    )

    with pytest.raises(LookupError, match="Organization not found"):
        await project_service.create_project(
            session=mock_session,
            organization_id=1,
            project_data=ProjectCreate(name="Backend API"),
            current_user=current_user,
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_project_rollbacks_on_integrity_error(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    monkeypatch.setattr(
        project_service,
        "generate_unique_project_slug",
        AsyncMock(return_value="backend-api"),
    )

    mock_session.commit.side_effect = IntegrityError(
        statement="INSERT INTO projects",
        params={},
        orig=Exception("duplicate key"),
    )

    with pytest.raises(IntegrityError):
        await project_service.create_project(
            session=mock_session,
            organization_id=1,
            project_data=ProjectCreate(name="Backend API"),
            current_user=current_user,
        )

    mock_session.rollback.assert_awaited_once()
    mock_session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_organization_projects_success(
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
) -> None:
    mock_session.scalar.return_value = 1

    scalars_result = MagicMock()
    scalars_result.all.return_value = [sample_project]
    mock_session.scalars.return_value = scalars_result

    result = await project_service.get_organization_projects(
        session=mock_session,
        organization_id=1,
        current_user=current_user,
    )

    assert result == [sample_project]
    mock_session.scalar.assert_awaited_once()
    mock_session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_organization_projects_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
) -> None:
    mock_session.scalar.return_value = None

    with pytest.raises(LookupError, match="Organization not found"):
        await project_service.get_organization_projects(
            session=mock_session,
            organization_id=1,
            current_user=current_user,
        )

    mock_session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_project_by_id_success(
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
) -> None:
    mock_session.scalar.return_value = sample_project

    result = await project_service.get_project_by_id(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
    )

    assert result == sample_project
    mock_session.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_by_id_not_found(
    mock_session: AsyncMock,
    current_user: User,
) -> None:
    mock_session.scalar.return_value = None

    with pytest.raises(LookupError, match="Project not found"):
        await project_service.get_project_by_id(
            session=mock_session,
            organization_id=1,
            project_id=999,
            current_user=current_user,
        )


@pytest.mark.asyncio
async def test_get_organization_projects_excludes_inactive_projects(
    mock_session: AsyncMock,
    current_user: User,
) -> None:
    mock_session.scalar.return_value = 1

    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    mock_session.scalars.return_value = scalars_result

    result = await project_service.get_organization_projects(
        session=mock_session,
        organization_id=1,
        current_user=current_user,
    )

    assert result == []
    mock_session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_organization_projects_rejects_other_organization(
    mock_session: AsyncMock,
    current_user: User,
) -> None:
    mock_session.scalar.return_value = None

    with pytest.raises(LookupError, match="Organization not found"):
        await project_service.get_organization_projects(
            session=mock_session,
            organization_id=2,
            current_user=current_user,
        )

    mock_session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_project_by_id_rejects_other_organization(
    mock_session: AsyncMock,
    current_user: User,
) -> None:
    mock_session.scalar.return_value = None

    with pytest.raises(LookupError, match="Project not found"):
        await project_service.get_project_by_id(
            session=mock_session,
            organization_id=2,
            project_id=1,
            current_user=current_user,
        )


@pytest.mark.asyncio
async def test_get_project_by_id_rejects_inactive_project(
    mock_session: AsyncMock,
    current_user: User,
) -> None:
    mock_session.scalar.return_value = None

    with pytest.raises(LookupError, match="Project not found"):
        await project_service.get_project_by_id(
            session=mock_session,
            organization_id=1,
            project_id=1,
            current_user=current_user,
        )


def test_list_projects_success(
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=[sample_project])
    monkeypatch.setattr(
        projects_endpoint,
        "get_organization_projects",
        service,
    )

    response = client.get("/api/v1/organizations/1/projects")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": sample_project.id,
            "organization_id": sample_project.organization_id,
            "name": sample_project.name,
            "slug": sample_project.slug,
            "description": sample_project.description,
            "is_active": sample_project.is_active,
        }
    ]

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        current_user=current_user,
    )


def test_list_projects_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=LookupError)
    monkeypatch.setattr(
        projects_endpoint,
        "get_organization_projects",
        service,
    )

    response = client.get("/api/v1/organizations/999/projects")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_get_project_success(
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_project)
    monkeypatch.setattr(
        projects_endpoint,
        "get_project_by_id",
        service,
    )

    response = client.get("/api/v1/organizations/1/projects/1")

    assert response.status_code == 200
    assert response.json() == {
        "id": sample_project.id,
        "organization_id": sample_project.organization_id,
        "name": sample_project.name,
        "slug": sample_project.slug,
        "description": sample_project.description,
        "is_active": sample_project.is_active,
    }

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
    )


def test_get_project_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=LookupError)
    monkeypatch.setattr(
        projects_endpoint,
        "get_project_by_id",
        service,
    )

    response = client.get("/api/v1/organizations/1/projects/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_project_update_accepts_name() -> None:
    update = ProjectUpdate(name="New project name")

    assert update.name == "New project name"


def test_project_update_accepts_description() -> None:
    update = ProjectUpdate(description="Updated description")

    assert update.description == "Updated description"


def test_project_update_allows_clearing_description() -> None:
    update = ProjectUpdate(description=None)

    assert update.description is None
    assert "description" in update.model_fields_set


def test_project_update_rejects_null_name() -> None:
    with pytest.raises(ValidationError):
        ProjectUpdate(name=None)


def test_project_update_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError):
        ProjectUpdate()


def test_project_update_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ProjectUpdate(unknown="value")  # type: ignore[call-arg]


async def test_update_project_success(
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    monkeypatch.setattr(
        project_service,
        "generate_unique_project_slug",
        AsyncMock(return_value="new-project-name"),
    )

    mock_session.scalar.return_value = sample_project

    update_data = ProjectUpdate(
        name="New project name",
        description="Updated description",
    )

    result = await project_service.update_project(
        mock_session,
        1,
        1,
        update_data,
        current_user,
    )

    assert result.name == "New project name"
    assert result.slug == "new-project-name"
    assert result.description == "Updated description"

    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(sample_project)


async def test_update_project_without_name_change(
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )

    mock_session.scalar.return_value = sample_project

    update_data = ProjectUpdate(description="New description")

    result = await project_service.update_project(
        mock_session,
        1,
        1,
        update_data,
        current_user,
    )

    assert result.description == "New description"
    assert result.slug == "backend-api"

    mock_session.commit.assert_awaited_once()


async def test_update_project_clears_description(
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )

    mock_session.scalar.return_value = sample_project

    update_data = ProjectUpdate(description=None)

    result = await project_service.update_project(
        mock_session,
        1,
        1,
        update_data,
        current_user,
    )

    assert result.description is None
    mock_session.commit.assert_awaited_once()


async def test_update_project_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=None),
    )

    with pytest.raises(LookupError, match="Organization not found"):
        await project_service.update_project(
            mock_session,
            1,
            1,
            ProjectUpdate(name="New name"),
            current_user,
        )

    mock_session.scalar.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


async def test_update_project_not_found(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )

    mock_session.scalar.return_value = None

    with pytest.raises(LookupError, match="Project not found"):
        await project_service.update_project(
            mock_session,
            1,
            999,
            ProjectUpdate(name="New name"),
            current_user,
        )

    mock_session.commit.assert_not_awaited()


async def test_update_project_rolls_back_on_integrity_error(
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    monkeypatch.setattr(
        project_service,
        "generate_unique_project_slug",
        AsyncMock(return_value="new-project-name"),
    )

    mock_session.scalar.return_value = sample_project
    mock_session.commit.side_effect = IntegrityError(
        "UPDATE",
        {},
        Exception("duplicate slug"),
    )

    with pytest.raises(IntegrityError):
        await project_service.update_project(
            mock_session,
            1,
            1,
            ProjectUpdate(name="New project name"),
            current_user,
        )

    mock_session.rollback.assert_awaited_once()
    mock_session.refresh.assert_not_awaited()


def test_update_project_success_endpoint(
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_project)
    monkeypatch.setattr(
        projects_endpoint,
        "update_project",
        service,
    )

    response = client.patch(
        "/api/v1/organizations/1/projects/1",
        json={
            "name": "Updated project",
            "description": "Updated description",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == sample_project.id

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        project_id=1,
        project_data=ProjectUpdate(
            name="Updated project",
            description="Updated description",
        ),
        current_user=current_user,
    )


def test_update_project_not_found_endpoint(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=LookupError("Project not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "update_project",
        service,
    )

    response = client.patch(
        "/api/v1/organizations/1/projects/999",
        json={"name": "Updated project"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_update_project_organization_not_found_endpoint(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=LookupError("Organization not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "update_project",
        service,
    )

    response = client.patch(
        "/api/v1/organizations/999/projects/1",
        json={"name": "Updated project"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_update_project_invalid_payload_endpoint(
    client: TestClient,
) -> None:
    response = client.patch(
        "/api/v1/organizations/1/projects/1",
        json={"name": None},
    )

    assert response.status_code == 422
