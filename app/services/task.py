from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.project import Project
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.exceptions import (
    OrganizationNotFoundError,
    ProjectNotFoundError,
    TaskAssigneeNotFoundError,
    TaskNotFoundError,
)
from app.services.organization import (
    _get_active_organization_membership,
    _get_active_organization_membership_for_update,
)


async def _get_active_project(
    session: AsyncSession,
    organization_id: int,
    project_id: int,
) -> Project | None:
    return await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.organization_id == organization_id,
            Project.is_active.is_(True),
        )
    )


async def create_task(
    session: AsyncSession,
    organization_id: int,
    task_data: TaskCreate,
    current_user: User,
) -> Task:
    membership = await _get_active_organization_membership_for_update(
        session,
        organization_id,
        current_user.id,
    )

    if membership is None:
        raise OrganizationNotFoundError("Organization not found")

    project = await _get_active_project(
        session,
        organization_id,
        task_data.project_id,
    )

    if project is None:
        raise ProjectNotFoundError("Project not found")

    if task_data.assignee_id is not None:
        assignee_membership = await _get_active_organization_membership_for_update(
            session,
            organization_id,
            task_data.assignee_id,
        )

        if assignee_membership is None:
            raise TaskAssigneeNotFoundError("Task assignee not found")

    task = Task(
        organization_id=organization_id,
        project_id=task_data.project_id,
        assignee_id=task_data.assignee_id,
        title=task_data.title,
        description=task_data.description,
        priority=task_data.priority,
        due_date=task_data.due_date,
    )

    session.add(task)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise

    await session.refresh(task)

    return task


async def get_project_tasks(
    session: AsyncSession,
    organization_id: int,
    project_id: int,
    current_user: User,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    assignee_id: int | None = None,
    search: str | None = None,
) -> list[Task]:
    membership = await _get_active_organization_membership(
        session,
        organization_id,
        current_user.id,
    )

    if membership is None:
        raise OrganizationNotFoundError("Organization not found")

    project = await _get_active_project(
        session,
        organization_id,
        project_id,
    )

    if project is None:
        raise ProjectNotFoundError("Project not found")

    query = select(Task).where(
        Task.organization_id == organization_id,
        Task.project_id == project_id,
        Task.is_active.is_(True),
    )

    if status is not None:
        query = query.where(Task.status == status)

    if priority is not None:
        query = query.where(Task.priority == priority)

    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)

    if search and search.strip():
        query = query.where(Task.title.ilike(f"%{search.strip()}%"))

    query = query.order_by(Task.created_at.desc())

    result = await session.scalars(query)

    return list(result.all())


async def get_task_by_id(
    session: AsyncSession,
    organization_id: int,
    task_id: int,
    current_user: User,
) -> Task:
    membership = await _get_active_organization_membership(
        session,
        organization_id,
        current_user.id,
    )

    if membership is None:
        raise OrganizationNotFoundError("Organization not found")

    task = await session.scalar(
        select(Task)
        .join(
            Organization,
            Organization.id == Task.organization_id,
        )
        .where(
            Task.id == task_id,
            Task.organization_id == organization_id,
            Task.is_active.is_(True),
            Organization.is_active.is_(True),
        )
    )

    if task is None:
        raise TaskNotFoundError("Task not found")

    return task


async def update_task(
    session: AsyncSession,
    organization_id: int,
    task_id: int,
    task_data: TaskUpdate,
    current_user: User,
) -> Task:
    membership = await _get_active_organization_membership_for_update(
        session,
        organization_id,
        current_user.id,
    )

    if membership is None:
        raise OrganizationNotFoundError("Organization not found")

    task = await session.scalar(
        select(Task)
        .where(
            Task.id == task_id,
            Task.organization_id == organization_id,
            Task.is_active.is_(True),
        )
        .with_for_update()
    )

    if task is None:
        raise TaskNotFoundError("Task not found")

    update_data = task_data.model_dump(exclude_unset=True)

    if "title" in update_data:
        if update_data["title"] is None:
            raise ValueError("Task title cannot be null")
        task.title = update_data["title"]

    if "description" in update_data:
        task.description = update_data["description"]

    if "assignee_id" in update_data:
        assignee_id = update_data["assignee_id"]

        if assignee_id is not None:
            assignee_membership = await _get_active_organization_membership_for_update(
                session,
                organization_id,
                assignee_id,
            )

            if assignee_membership is None:
                raise TaskAssigneeNotFoundError("Task assignee not found")

        task.assignee_id = assignee_id

    if "status" in update_data:
        if update_data["status"] is None:
            raise ValueError("Task status cannot be null")
        task.status = update_data["status"]

    if "priority" in update_data:
        if update_data["priority"] is None:
            raise ValueError("Task priority cannot be null")
        task.priority = update_data["priority"]

    if "due_date" in update_data:
        task.due_date = update_data["due_date"]

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise

    await session.refresh(task)

    return task


async def deactivate_task(
    session: AsyncSession,
    organization_id: int,
    task_id: int,
    current_user: User,
) -> None:
    membership = await _get_active_organization_membership_for_update(
        session,
        organization_id,
        current_user.id,
    )

    if membership is None:
        raise OrganizationNotFoundError("Organization not found")

    task = await session.scalar(
        select(Task)
        .where(
            Task.id == task_id,
            Task.organization_id == organization_id,
            Task.is_active.is_(True),
        )
        .with_for_update()
    )

    if task is None:
        raise TaskNotFoundError("Task not found")

    task.is_active = False

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
