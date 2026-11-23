from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.api.v1.endpoints import tasks as tasks_endpoint
from app.api.v1.endpoints.tasks import router
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.exceptions import (
    OrganizationNotFoundError,
    ProjectNotFoundError,
    TaskAssigneeNotFoundError,
    TaskNotFoundError,
)
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


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_task_create_uses_default_priority() -> None:
    task_data = TaskCreate(
        project_id=1,
        title="Implement authentication",
    )

    assert task_data.priority == TaskPriority.MEDIUM
    assert task_data.assignee_id is None
    assert task_data.due_date is None


def test_task_create_accepts_assignee() -> None:
    task_data = TaskCreate(
        project_id=1,
        title="Implement authentication",
        assignee_id=2,
    )

    assert task_data.assignee_id == 2


def test_task_create_rejects_invalid_project_id() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(project_id=0, title="Implement authentication")


def test_task_create_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(project_id=1, title="")


def test_task_update_accepts_title() -> None:
    update = TaskUpdate(title="Updated task")

    assert update.title == "Updated task"


def test_task_update_accepts_status_and_priority() -> None:
    update = TaskUpdate(
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
    )

    assert update.status == TaskStatus.IN_PROGRESS
    assert update.priority == TaskPriority.HIGH


def test_task_update_allows_clearing_description() -> None:
    update = TaskUpdate(description=None)

    assert update.description is None
    assert "description" in update.model_fields_set


def test_task_update_allows_clearing_assignee() -> None:
    update = TaskUpdate(assignee_id=None)

    assert update.assignee_id is None
    assert "assignee_id" in update.model_fields_set


def test_task_update_rejects_invalid_assignee_id() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(assignee_id=0)


# ---------------------------------------------------------------------------
# List tasks endpoint
# ---------------------------------------------------------------------------


def test_list_project_tasks_success(
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=[sample_task])
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = client.get(
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
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
    query_params: dict[str, str],
    expected_kwargs: dict[str, object],
) -> None:
    service = AsyncMock(return_value=[sample_task])
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = client.get(
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
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=[sample_task])
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = client.get(
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
    client: TestClient,
    query_params: dict[str, str],
) -> None:
    response = client.get(
        "/api/v1/organizations/1/projects/1/tasks",
        params=query_params,
    )

    assert response.status_code == 422


def test_list_project_tasks_organization_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = client.get(
        "/api/v1/organizations/999/projects/1/tasks",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_list_project_tasks_project_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=ProjectNotFoundError("Project not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = client.get(
        "/api/v1/organizations/1/projects/999/tasks",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


# ---------------------------------------------------------------------------
# Get task endpoint
# ---------------------------------------------------------------------------


def test_get_task_success(
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "get_task_by_id", service)

    response = client.get("/api/v1/organizations/1/tasks/1")

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
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskNotFoundError("Task not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "get_task_by_id", service)

    response = client.get("/api/v1/organizations/1/tasks/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_get_task_organization_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "get_task_by_id", service)

    response = client.get("/api/v1/organizations/999/tasks/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


# ---------------------------------------------------------------------------
# Create task endpoint
# ---------------------------------------------------------------------------


def test_create_task_success(
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = client.post(
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
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_task.assignee_id = 2

    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = client.post(
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
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = client.post(
        "/api/v1/organizations/999/tasks",
        json={
            "project_id": 1,
            "title": "Implement authentication",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_create_task_project_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=ProjectNotFoundError("Project not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = client.post(
        "/api/v1/organizations/1/tasks",
        json={
            "project_id": 999,
            "title": "Implement authentication",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_create_task_assignee_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskAssigneeNotFoundError("Task assignee not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "create_task", service)

    response = client.post(
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
    client: TestClient,
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

    response = client.post(
        "/api/v1/organizations/1/tasks",
        json={
            "project_id": 1,
            "title": "Implement authentication",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Task could not be created"}


def test_create_task_invalid_payload(
    client: TestClient,
) -> None:
    response = client.post(
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
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = client.patch(
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
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskNotFoundError("Task not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = client.patch(
        "/api/v1/organizations/1/tasks/999",
        json={"title": "Updated task"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_update_task_organization_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = client.patch(
        "/api/v1/organizations/999/tasks/1",
        json={"title": "Updated task"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_update_task_assignee_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskAssigneeNotFoundError("Task assignee not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={"assignee_id": 999},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task assignee not found"}


def test_update_task_integrity_error(
    client: TestClient,
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

    response = client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={"title": "Updated task"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Task could not be updated"}


def test_update_task_invalid_payload(
    client: TestClient,
) -> None:
    response = client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={"priority": "invalid"},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Deactivate task endpoint
# ---------------------------------------------------------------------------


def test_deactivate_task_success(
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=None)
    monkeypatch.setattr(tasks_endpoint, "deactivate_task", service)

    response = client.delete("/api/v1/organizations/1/tasks/1")

    assert response.status_code == 204
    assert response.content == b""

    service.assert_awaited_once_with(
        session=mock_session,
        organization_id=1,
        task_id=1,
        current_user=current_user,
    )


def test_deactivate_task_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=TaskNotFoundError("Task not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "deactivate_task", service)

    response = client.delete("/api/v1/organizations/1/tasks/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_deactivate_task_organization_not_found(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(
        side_effect=OrganizationNotFoundError("Organization not found"),
    )
    monkeypatch.setattr(tasks_endpoint, "deactivate_task", service)

    response = client.delete("/api/v1/organizations/999/tasks/1")

    assert response.status_code == 404
    assert response.json() == {"detail": "Organization not found"}


def test_list_project_tasks_empty(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=[])
    monkeypatch.setattr(tasks_endpoint, "get_project_tasks", service)

    response = client.get(
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
    client: TestClient,
    payload: dict[str, object],
) -> None:
    response = client.post(
        "/api/v1/organizations/1/tasks",
        json=payload,
    )

    assert response.status_code == 422


def test_update_task_clears_nullable_fields(
    client: TestClient,
    mock_session: AsyncMock,
    current_user: User,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock(return_value=sample_task)
    monkeypatch.setattr(tasks_endpoint, "update_task", service)

    response = client.patch(
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
    client: TestClient,
    assignee_id: int,
) -> None:
    response = client.patch(
        "/api/v1/organizations/1/tasks/1",
        json={"assignee_id": assignee_id},
    )

    assert response.status_code == 422


def test_list_project_tasks_search_too_long(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/organizations/1/projects/1/tasks",
        params={"search": "a" * 201},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field",
    ["title", "status", "priority"],
)
def test_task_update_rejects_null_non_nullable_fields(
    field: str,
) -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(**{field: None})


def test_task_update_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate()


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
    client: TestClient,
    payload: dict[str, object],
) -> None:
    response = client.patch(
        "/api/v1/organizations/1/tasks/1",
        json=payload,
    )

    assert response.status_code == 422
