from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.organization_member import OrganizationMember
from app.models.project import Project
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import task as task_service
from app.services.exceptions import (
    OrganizationNotFoundError,
    ProjectNotFoundError,
    TaskAssigneeNotFoundError,
    TaskNotFoundError,
)
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def sample_task() -> Task:
    return Task(
        id=1,
        organization_id=1,
        project_id=1,
        title="Implement authentication",
        description="Add JWT authentication",
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_create_task_success(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership_mock = AsyncMock(return_value=owner_membership)
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        membership_mock,
    )

    mock_session.scalar.return_value = sample_project

    result = await task_service.create_task(
        session=mock_session,
        organization_id=1,
        task_data=TaskCreate(
            project_id=1,
            title="Implement authentication",
            description="Add JWT authentication",
            priority=TaskPriority.HIGH,
        ),
        current_user=current_user,
    )

    assert result.title == "Implement authentication"
    assert result.description == "Add JWT authentication"
    assert result.organization_id == 1
    assert result.project_id == 1
    assert result.priority == TaskPriority.HIGH
    assert result.assignee_id is None

    mock_session.add.assert_called_once_with(result)
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_create_task_with_assignee(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership_mock = AsyncMock(return_value=owner_membership)
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        membership_mock,
    )

    mock_session.scalar.return_value = sample_project

    result = await task_service.create_task(
        session=mock_session,
        organization_id=1,
        task_data=TaskCreate(
            project_id=1,
            title="Implement authentication",
            assignee_id=1,
        ),
        current_user=current_user,
    )

    assert result.assignee_id == 1
    assert membership_mock.await_count == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_task_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=None),
    )

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
        await task_service.create_task(
            session=mock_session,
            organization_id=1,
            task_data=TaskCreate(
                project_id=1,
                title="Implement authentication",
            ),
            current_user=current_user,
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_project_not_found(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = None

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
        await task_service.create_task(
            session=mock_session,
            organization_id=1,
            task_data=TaskCreate(
                project_id=999,
                title="Implement authentication",
            ),
            current_user=current_user,
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_rejects_invalid_assignee(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership_mock = AsyncMock(
        side_effect=[owner_membership, None],
    )
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        membership_mock,
    )
    mock_session.scalar.return_value = sample_project

    with pytest.raises(
        TaskAssigneeNotFoundError,
        match="Task assignee not found",
    ):
        await task_service.create_task(
            session=mock_session,
            organization_id=1,
            task_data=TaskCreate(
                project_id=1,
                title="Implement authentication",
                assignee_id=999,
            ),
            current_user=current_user,
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_task_rolls_back_on_integrity_error(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_project
    mock_session.commit.side_effect = IntegrityError(
        "INSERT INTO tasks",
        {},
        Exception("database error"),
    )

    with pytest.raises(IntegrityError):
        await task_service.create_task(
            session=mock_session,
            organization_id=1,
            task_data=TaskCreate(
                project_id=1,
                title="Implement authentication",
            ),
            current_user=current_user,
        )

    mock_session.rollback.assert_awaited_once()
    mock_session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_project_tasks_success(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_project
    mock_session.scalars.return_value = MagicMock()
    mock_session.scalars.return_value.all.return_value = [sample_task]

    result = await task_service.get_project_tasks(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
    )

    assert result == [sample_task]
    mock_session.scalars.assert_awaited_once()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_project_tasks_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=None),
    )

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
        await task_service.get_project_tasks(
            session=mock_session,
            organization_id=1,
            project_id=1,
            current_user=current_user,
        )

    mock_session.scalar.assert_not_awaited()
    mock_session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_project_tasks_project_not_found(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = None

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
        await task_service.get_project_tasks(
            session=mock_session,
            organization_id=1,
            project_id=999,
            current_user=current_user,
        )

    mock_session.scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_task_by_id_success(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_task

    result = await task_service.get_task_by_id(
        session=mock_session,
        organization_id=1,
        task_id=1,
        current_user=current_user,
    )

    assert result == sample_task
    mock_session.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_task_by_id_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=None),
    )

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
        await task_service.get_task_by_id(
            session=mock_session,
            organization_id=1,
            task_id=1,
            current_user=current_user,
        )

    mock_session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_task_by_id_not_found(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = None

    with pytest.raises(TaskNotFoundError, match="Task not found"):
        await task_service.get_task_by_id(
            session=mock_session,
            organization_id=1,
            task_id=999,
            current_user=current_user,
        )


@pytest.mark.asyncio
async def test_update_task_success(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_task

    result = await task_service.update_task(
        session=mock_session,
        organization_id=1,
        task_id=1,
        task_data=TaskUpdate(
            title="Updated task",
            description="Updated description",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
        ),
        current_user=current_user,
    )

    assert result.title == "Updated task"
    assert result.description == "Updated description"
    assert result.status == TaskStatus.IN_PROGRESS
    assert result.priority == TaskPriority.HIGH

    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(sample_task)


@pytest.mark.asyncio
async def test_update_task_clears_assignee(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_task.assignee_id = 2

    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_task

    result = await task_service.update_task(
        session=mock_session,
        organization_id=1,
        task_id=1,
        task_data=TaskUpdate(assignee_id=None),
        current_user=current_user,
    )

    assert result.assignee_id is None
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_task_with_assignee(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership_mock = AsyncMock(return_value=owner_membership)
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        membership_mock,
    )
    mock_session.scalar.return_value = sample_task

    result = await task_service.update_task(
        session=mock_session,
        organization_id=1,
        task_id=1,
        task_data=TaskUpdate(assignee_id=2),
        current_user=current_user,
    )

    assert result.assignee_id == 2
    assert membership_mock.await_count == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_task_rejects_invalid_assignee(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership_mock = AsyncMock(
        side_effect=[owner_membership, None],
    )
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        membership_mock,
    )
    mock_session.scalar.return_value = sample_task

    with pytest.raises(
        TaskAssigneeNotFoundError,
        match="Task assignee not found",
    ):
        await task_service.update_task(
            session=mock_session,
            organization_id=1,
            task_id=1,
            task_data=TaskUpdate(assignee_id=999),
            current_user=current_user,
        )

    mock_session.commit.assert_not_awaited()
    mock_session.refresh.assert_not_awaited()


def test_update_task_rejects_null_title() -> None:
    with pytest.raises(ValidationError, match="Field cannot be null"):
        TaskUpdate(title=None)


@pytest.mark.asyncio
async def test_update_task_not_found(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = None

    with pytest.raises(TaskNotFoundError, match="Task not found"):
        await task_service.update_task(
            session=mock_session,
            organization_id=1,
            task_id=999,
            task_data=TaskUpdate(title="Updated task"),
            current_user=current_user,
        )

    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=None),
    )

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
        await task_service.update_task(
            session=mock_session,
            organization_id=1,
            task_id=1,
            task_data=TaskUpdate(title="Updated task"),
            current_user=current_user,
        )

    mock_session.scalar.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_task_rolls_back_on_integrity_error(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_task
    mock_session.commit.side_effect = IntegrityError(
        "UPDATE tasks",
        {},
        Exception("database error"),
    )

    with pytest.raises(IntegrityError):
        await task_service.update_task(
            session=mock_session,
            organization_id=1,
            task_id=1,
            task_data=TaskUpdate(title="Updated task"),
            current_user=current_user,
        )

    mock_session.rollback.assert_awaited_once()
    mock_session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_deactivate_task_success(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_task

    await task_service.deactivate_task(
        session=mock_session,
        organization_id=1,
        task_id=1,
        current_user=current_user,
    )

    assert sample_task.is_active is False
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_deactivate_task_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=None),
    )

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
        await task_service.deactivate_task(
            session=mock_session,
            organization_id=1,
            task_id=1,
            current_user=current_user,
        )

    mock_session.scalar.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_deactivate_task_not_found(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = None

    with pytest.raises(TaskNotFoundError, match="Task not found"):
        await task_service.deactivate_task(
            session=mock_session,
            organization_id=1,
            task_id=999,
            current_user=current_user,
        )

    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_deactivate_task_rolls_back_on_integrity_error(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_task
    mock_session.commit.side_effect = IntegrityError(
        "UPDATE tasks",
        {},
        Exception("database error"),
    )

    with pytest.raises(IntegrityError):
        await task_service.deactivate_task(
            session=mock_session,
            organization_id=1,
            task_id=1,
            current_user=current_user,
        )

    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_tasks_filters_by_status(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_project

    scalars_result = MagicMock()
    scalars_result.all.return_value = [sample_task]
    mock_session.scalars.return_value = scalars_result

    result = await task_service.get_project_tasks(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
        status=TaskStatus.IN_PROGRESS,
    )

    assert result == [sample_task]
    mock_session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_tasks_filters_by_priority(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_project

    scalars_result = MagicMock()
    scalars_result.all.return_value = [sample_task]
    mock_session.scalars.return_value = scalars_result

    result = await task_service.get_project_tasks(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
        priority=TaskPriority.HIGH,
    )

    assert result == [sample_task]
    mock_session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_tasks_filters_by_assignee(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    sample_task.assignee_id = 2
    mock_session.scalar.return_value = 1

    scalars_result = MagicMock()
    scalars_result.all.return_value = [sample_task]
    mock_session.scalars.return_value = scalars_result

    result = await task_service.get_project_tasks(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
        assignee_id=2,
    )

    assert result == [sample_task]
    mock_session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_tasks_filters_by_search(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_project

    scalars_result = MagicMock()
    scalars_result.all.return_value = [sample_task]
    mock_session.scalars.return_value = scalars_result

    result = await task_service.get_project_tasks(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
        search="authentication",
    )

    assert result == [sample_task]
    mock_session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_tasks_combines_filters(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    sample_task.assignee_id = 2
    mock_session.scalar.return_value = sample_project

    scalars_result = MagicMock()
    scalars_result.all.return_value = [sample_task]
    mock_session.scalars.return_value = scalars_result

    result = await task_service.get_project_tasks(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        assignee_id=2,
        search="authentication",
    )

    assert result == [sample_task]
    mock_session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_project_tasks_without_filters(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
    sample_task: Task,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        task_service,
        "_get_active_organization_membership",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = sample_project

    scalars_result = MagicMock()
    scalars_result.all.return_value = [sample_task]
    mock_session.scalars.return_value = scalars_result

    result = await task_service.get_project_tasks(
        session=mock_session,
        organization_id=1,
        project_id=1,
        current_user=current_user,
    )

    assert result == [sample_task]
    mock_session.scalars.assert_awaited_once()
