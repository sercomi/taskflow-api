from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.api.v1.endpoints import tasks as tasks_endpoint
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.exceptions import (
    OrganizationNotFoundError,
    ProjectNotFoundError,
    TaskAssigneeNotFoundError,
    TaskNotFoundError,
)
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def sample_task() -> Task:
    now = datetime.now(UTC)

    return Task(
        id=1,
        organization_id=1,
        project_id=1,
        assignee_id=None,
        title="Implement authentication",
        description="Implement JWT authentication",
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        due_date=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def test_list_project_tasks_success(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=[sample_task])
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = tasks_client.get(
        "/api/v1/organizations/1/projects/1/tasks",
    )

    assert response.status_code == 200
    task_response = response.json()[0]

    assert task_response["id"] == sample_task.id
    assert task_response["organization_id"] == sample_task.organization_id
    assert task_response["project_id"] == sample_task.project_id
    assert task_response["assignee_id"] is None
    assert task_response["title"] == sample_task.title
    assert task_response["description"] == sample_task.description
    assert task_response["status"] == TaskStatus.TODO.value
    assert task_response["priority"] == TaskPriority.MEDIUM.value
    assert task_response["due_date"] is None
    assert task_response["is_active"] is True
    assert task_response["created_at"] is not None
    assert task_response["updated_at"] is not None

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
        status=None,
        priority=None,
        assignee_id=None,
        search=None,
    )


@pytest.mark.parametrize(
    ("query_params", "expected_kwargs"),
    [
        (
            {"status": "in_progress"},
            {
                "status": TaskStatus.IN_PROGRESS,
                "priority": None,
                "assignee_id": None,
                "search": None,
            },
        ),
        (
            {"priority": "high"},
            {
                "status": None,
                "priority": TaskPriority.HIGH,
                "assignee_id": None,
                "search": None,
            },
        ),
        (
            {"assignee_id": "2"},
            {
                "status": None,
                "priority": None,
                "assignee_id": 2,
                "search": None,
            },
        ),
        (
            {"search": "authentication"},
            {
                "status": None,
                "priority": None,
                "assignee_id": None,
                "search": "authentication",
            },
        ),
    ],
    ids=["status", "priority", "assignee", "search"],
)
def test_list_project_tasks_with_individual_filters(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
    query_params: dict[str, str],
    expected_kwargs: dict[str, object],
) -> None:
    service = AsyncMock(return_value=[sample_task])
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = tasks_client.get(
        "/api/v1/organizations/1/projects/1/tasks",
        params=query_params,
    )

    assert response.status_code == 200

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
        **expected_kwargs,
    )


def test_list_project_tasks_with_combined_filters(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=[sample_task])
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = tasks_client.get(
        "/api/v1/organizations/1/projects/1/tasks",
        params={
            "status": "in_progress",
            "priority": "high",
            "assignee_id": "2",
            "search": "authentication",
        },
    )

    assert response.status_code == 200

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        assignee_id=2,
        search="authentication",
    )


@pytest.mark.parametrize(
    "query_params",
    [
        {"status": "invalid"},
        {"priority": "invalid"},
        {"assignee_id": "0"},
        {"assignee_id": "-1"},
        {"search": ""},
    ],
    ids=[
        "invalid-status",
        "invalid-priority",
        "zero-assignee",
        "negative-assignee",
        "empty-search",
    ],
)
def test_list_project_tasks_invalid_filters(
    tasks_client: TestClient,
    query_params: dict[str, str],
) -> None:
    response = tasks_client.get(
        "/api/v1/organizations/1/projects/1/tasks",
        params=query_params,
    )

    assert response.status_code == 422


def test_list_project_tasks_organization_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = tasks_client.get(
        "/api/v1/organizations/999/projects/1/tasks",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_list_project_tasks_project_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=ProjectNotFoundError("Project not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = tasks_client.get(
        "/api/v1/organizations/1/projects/999/tasks",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


# ---------------------------------------------------------------------------
# Get task endpoint
# ---------------------------------------------------------------------------


def test_get_task_success(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "get_task_by_id", service)

    response = tasks_client.get("/api/v1/organizations/1/tasks/1")

    assert response.status_code == 200
    assert response.json()["id"] == sample_task.id
    assert response.json()["title"] == sample_task.title
    assert response.json()["status"] == TaskStatus.TODO.value
    assert response.json()["priority"] == TaskPriority.MEDIUM.value

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        task_id=1,
        current_user=current_user,
    )


def test_get_task_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskNotFoundError("Task not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "get_task_by_id", service)

    response = tasks_client.get("/api/v1/organizations/1/tasks/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_get_task_organization_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "get_task_by_id", service)

    response = tasks_client.get("/api/v1/organizations/999/tasks/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


# ---------------------------------------------------------------------------
# Create task endpoint
# ---------------------------------------------------------------------------


def test_create_task_success(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = tasks_client.post(
        "/api/v1/organizations/1/tasks",
        json={
            "project_id": 1,
            "title": "Implement authentication",
            "description": "Implement JWT authentication",
            "priority": "medium",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == sample_task.id
    assert response.json()["title"] == sample_task.title

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        task_data=TaskCreate(
            project_id=1,
            title="Implement authentication",
            description="Implement JWT authentication",
            priority=TaskPriority.MEDIUM,
        ),
        current_user=current_user,
    )


def test_create_task_with_assignee(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_task.assignee_id = 2

    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = tasks_client.post(
        "/api/v1/organizations/1/tasks",
        json={
            "project_id": 1,
            "title": "Implement authentication",
            "assignee_id": 2,
        },
    )

    assert response.status_code == 201
    assert response.json()["assignee_id"] == 2

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        task_data=TaskCreate(
            project_id=1,
            title="Implement authentication",
            assignee_id=2,
        ),
        current_user=current_user,
    )


def test_create_task_organization_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = tasks_client.post(
        "/api/v1/organizations/999/tasks",
        json={
            "project_id": 1,
            "title": "Implement authentication",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_create_task_project_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=ProjectNotFoundError("Project not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = tasks_client.post(
        "/api/v1/organizations/1/tasks",
        json={
            "project_id": 999,
            "title": "Implement authentication",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_create_task_assignee_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskAssigneeNotFoundError("Task assignee not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = tasks_client.post(
        "/api/v1/organizations/1/tasks",
        json={
            "project_id": 1,
            "title": "Implement authentication",
            "assignee_id": 999,
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task assignee not found"}


def test_create_task_integrity_error(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=IntegrityError(
            "INSERT",
            {},
            Exception("database error"),
        ),
    )
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = tasks_client.post(
        "/api/v1/organizations/1/tasks",
        json={
            "project_id": 1,
            "title": "Implement authentication",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Task could not be created"}


def test_create_task_invalid_payload(
    tasks_client: TestClient,
) -> None:
    response = tasks_client.post(
        "/api/v1/organizations/1/tasks",
        json={
            "project_id": 0,
            "title": "",
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Update task endpoint
# ---------------------------------------------------------------------------


def test_update_task_success(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = tasks_client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={
            "title": "Updated task",
            "status": "in_progress",
            "priority": "high",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == sample_task.id

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        task_id=1,
        task_data=TaskUpdate(
            title="Updated task",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
        ),
        current_user=current_user,
    )


def test_update_task_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskNotFoundError("Task not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = tasks_client.patch(
        "/api/v1/organizations/1/tasks/999",
        json={"title": "Updated task"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_update_task_organization_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = tasks_client.patch(
        "/api/v1/organizations/999/tasks/1",
        json={"title": "Updated task"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_update_task_assignee_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskAssigneeNotFoundError("Task assignee not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = tasks_client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={"assignee_id": 999},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task assignee not found"}


def test_update_task_integrity_error(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=IntegrityError(
            "UPDATE",
            {},
            Exception("database error"),
        ),
    )
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = tasks_client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={"title": "Updated task"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Task could not be updated"}


def test_update_task_invalid_payload(
    tasks_client: TestClient,
) -> None:
    response = tasks_client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={"priority": "invalid"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Deactivate task endpoint
# ---------------------------------------------------------------------------


def test_deactivate_task_success(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=None)
    monkeypatch.setattr(tasks_endpoint, "deactivate_task", service)

    response = tasks_client.delete("/api/v1/organizations/1/tasks/1")

    assert response.status_code == 204
    assert response.content == b""

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        task_id=1,
        current_user=current_user,
    )


def test_deactivate_task_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskNotFoundError("Task not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "deactivate_task", service)

    response = tasks_client.delete("/api/v1/organizations/1/tasks/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_deactivate_task_organization_not_found(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "deactivate_task", service)

    response = tasks_client.delete("/api/v1/organizations/999/tasks/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_list_project_tasks_empty(
    tasks_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=[])
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = tasks_client.get(
        "/api/v1/organizations/1/projects/1/tasks",
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"project_id": 1},
        {"title": "Implement authentication"},
    ],
    ids=["empty-payload", "missing-title", "missing-project-id"],
)
def test_create_task_missing_required_fields(
    tasks_client: TestClient,
    payload: dict[str, object],
) -> None:
    response = tasks_client.post(
        "/api/v1/organizations/1/tasks",
        json=payload,
    )

    assert response.status_code == 422


def test_update_task_clears_nullable_fields(
    tasks_client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = tasks_client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={
            "description": None,
            "assignee_id": None,
            "due_date": None,
        },
    )

    assert response.status_code == 200

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        task_id=1,
        task_data=TaskUpdate(
            description=None,
            assignee_id=None,
            due_date=None,
        ),
        current_user=current_user,
    )


@pytest.mark.parametrize(
    "assignee_id",
    [0, -1],
    ids=["zero", "negative"],
)
def test_update_task_invalid_assignee_id(
    tasks_client: TestClient,
    assignee_id: int,
) -> None:
    response = tasks_client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={"assignee_id": assignee_id},
    )

    assert response.status_code == 422


def test_list_project_tasks_search_too_long(
    tasks_client: TestClient,
) -> None:
    response = tasks_client.get(
        "/api/v1/organizations/1/projects/1/tasks",
        params={"search": "a" * 201},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": None},
        {"status": None},
        {"priority": None},
    ],
    ids=[
        "empty-payload",
        "null-title",
        "null-status",
        "null-priority",
    ],
)
def test_update_task_rejects_invalid_payloads(
    tasks_client: TestClient,
    payload: dict[str, object],
) -> None:
    response = tasks_client.patch(
        "/api/v1/organizations/1/tasks/1",
        json=payload,
    )

    assert response.status_code == 422
