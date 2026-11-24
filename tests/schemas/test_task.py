import pytest
from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from pydantic import ValidationError


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


def test_task_create_allows_nullable_fields() -> None:
    task_data = TaskCreate(
        project_id=1,
        title="Implement authentication",
        description=None,
        assignee_id=None,
        due_date=None,
    )

    assert task_data.description is None
    assert task_data.assignee_id is None
    assert task_data.due_date is None
