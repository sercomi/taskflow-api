from unittest.mock import AsyncMock

import pytest
from app.api.v1.endpoints import projects as projects_endpoint
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.exceptions import OrganizationNotFoundError, ProjectNotFoundError
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


def test_create_project_endpoint_success(
    projects_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_project)
    monkeypatch.setattr(
        projects_endpoint,
        "create_project",
        service,
    )

    response = projects_client.post(
        "/api/v1/organizations/1/projects",
        json={
            "name": "Backend API",
            "description": "Backend project",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == sample_project.id
    assert response.json()["slug"] == sample_project.slug

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        project_data=ProjectCreate(
            name="Backend API",
            description="Backend project",
        ),
        current_user=current_user,
    )


def test_create_project_endpoint_organization_not_found(
    projects_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=OrganizationNotFoundError("Organization not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "create_project",
        service,
    )

    response = projects_client.post(
        "/api/v1/organizations/999/projects",
        json={"name": "Backend API"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_create_project_endpoint_integrity_error(
    projects_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=IntegrityError(
            "INSERT",
            {},
            Exception("duplicate slug"),
        )
    )
    monkeypatch.setattr(
        projects_endpoint,
        "create_project",
        service,
    )

    response = projects_client.post(
        "/api/v1/organizations/1/projects",
        json={"name": "Backend API"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Project already exists"}


def test_list_projects_success(
    projects_client: TestClient,
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

    response = projects_client.get("/api/v1/organizations/1/projects")

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
    projects_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=OrganizationNotFoundError("Organization not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "get_organization_projects",
        service,
    )

    response = projects_client.get("/api/v1/organizations/999/projects")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_get_project_success(
    projects_client: TestClient,
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

    response = projects_client.get("/api/v1/organizations/1/projects/1")

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
    projects_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=ProjectNotFoundError("Project not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "get_project_by_id",
        service,
    )

    response = projects_client.get("/api/v1/organizations/1/projects/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_update_project_success_endpoint(
    projects_client: TestClient,
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

    response = projects_client.patch(
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
    projects_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=ProjectNotFoundError("Project not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "update_project",
        service,
    )

    response = projects_client.patch(
        "/api/v1/organizations/1/projects/999",
        json={"name": "Updated project"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_update_project_organization_not_found_endpoint(
    projects_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=OrganizationNotFoundError("Organization not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "update_project",
        service,
    )

    response = projects_client.patch(
        "/api/v1/organizations/999/projects/1",
        json={"name": "Updated project"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_update_project_invalid_payload_endpoint(
    projects_client: TestClient,
) -> None:
    response = projects_client.patch(
        "/api/v1/organizations/1/projects/1",
        json={"name": None},
    )

    assert response.status_code == 422


def test_deactivate_project_endpoint_success(
    projects_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=None)
    monkeypatch.setattr(
        projects_endpoint,
        "deactivate_project",
        service,
    )

    response = projects_client.delete("/api/v1/organizations/1/projects/1")

    assert response.status_code == 204
    assert response.content == b""

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
    )


def test_deactivate_project_endpoint_not_found(
    projects_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=ProjectNotFoundError("Project not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "deactivate_project",
        service,
    )

    response = projects_client.delete("/api/v1/organizations/1/projects/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_deactivate_project_endpoint_organization_not_found(
    projects_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(side_effect=OrganizationNotFoundError("Organization not found"))
    monkeypatch.setattr(
        projects_endpoint,
        "deactivate_project",
        service,
    )

    response = projects_client.delete("/api/v1/organizations/999/projects/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_create_project_endpoint_invalid_organization_id(
    projects_client: TestClient,
) -> None:
    response = projects_client.post(
        "/api/v1/organizations/0/projects",
        json={"name": "Backend API"},
    )

    assert response.status_code == 422
