import pytest
from app.models.organization import Organization, OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.project import ProjectUpdate
from app.schemas.task import TaskUpdate
from app.services.exceptions import (
    OrganizationNotFoundError,
    ProjectNotFoundError,
    TaskNotFoundError,
)
from app.services.project import (
    deactivate_project,
    get_organization_projects,
    get_project_by_id,
    update_project,
)
from app.services.task import (
    deactivate_task,
    get_project_tasks,
    get_task_by_id,
    update_task,
)
from sqlalchemy.ext.asyncio import AsyncSession


async def test_user_cannot_access_other_organizations_resources(
    db_session: AsyncSession,
) -> None:
    user_a = User(
        email="tenant-a@example.com",
        username="tenant-a",
        hashed_password="hashed-password",
    )
    user_b = User(
        email="tenant-b@example.com",
        username="tenant-b",
        hashed_password="hashed-password",
    )

    organization_a = Organization(
        name="Organization A",
        slug="organization-a",
    )
    organization_b = Organization(
        name="Organization B",
        slug="organization-b",
    )

    db_session.add_all([user_a, user_b, organization_a, organization_b])
    await db_session.flush()

    membership_a = OrganizationMember(
        organization_id=organization_a.id,
        user_id=user_a.id,
        role=OrganizationRole.OWNER,
    )
    membership_b = OrganizationMember(
        organization_id=organization_b.id,
        user_id=user_b.id,
        role=OrganizationRole.OWNER,
    )

    project_a = Project(
        organization_id=organization_a.id,
        name="Project A",
        slug="project-a",
    )
    project_b = Project(
        organization_id=organization_b.id,
        name="Project B",
        slug="project-b",
    )

    db_session.add_all([membership_a, membership_b, project_a, project_b])
    await db_session.flush()

    task_a = Task(
        organization_id=organization_a.id,
        project_id=project_a.id,
        title="Task A",
    )
    task_b = Task(
        organization_id=organization_b.id,
        project_id=project_b.id,
        title="Task B",
    )

    db_session.add_all([task_a, task_b])
    await db_session.flush()

    # El usuario A puede acceder a sus propios recursos.
    own_project = await get_project_by_id(
        db_session,
        organization_a.id,
        project_a.id,
        user_a,
    )
    assert own_project.id == project_a.id

    own_task = await get_task_by_id(
        db_session,
        organization_a.id,
        task_a.id,
        user_a,
    )
    assert own_task.id == task_a.id

    # El usuario A no puede listar proyectos de B.
    with pytest.raises(OrganizationNotFoundError):
        await get_organization_projects(
            db_session,
            organization_b.id,
            user_a,
        )

    # Tampoco puede obtener un proyecto de B por su ID.
    with pytest.raises(ProjectNotFoundError):
        await get_project_by_id(
            db_session,
            organization_b.id,
            project_b.id,
            user_a,
        )

    # No puede listar tareas de un proyecto de B.
    with pytest.raises(OrganizationNotFoundError):
        await get_project_tasks(
            db_session,
            organization_b.id,
            project_b.id,
            user_a,
        )

    # Ni obtener una tarea de B por su ID.
    with pytest.raises(OrganizationNotFoundError):
        await get_task_by_id(
            db_session,
            organization_b.id,
            task_b.id,
            user_a,
        )


async def test_user_cannot_modify_other_organizations_resources(
    db_session: AsyncSession,
) -> None:
    user_a = User(
        email="write-tenant-a@example.com",
        username="write-tenant-a",
        hashed_password="hashed-password",
    )
    user_b = User(
        email="write-tenant-b@example.com",
        username="write-tenant-b",
        hashed_password="hashed-password",
    )

    organization_a = Organization(name="Write A", slug="write-a")
    organization_b = Organization(name="Write B", slug="write-b")

    db_session.add_all([user_a, user_b, organization_a, organization_b])
    await db_session.flush()

    db_session.add_all(
        [
            OrganizationMember(
                organization_id=organization_a.id,
                user_id=user_a.id,
                role=OrganizationRole.OWNER,
            ),
            OrganizationMember(
                organization_id=organization_b.id,
                user_id=user_b.id,
                role=OrganizationRole.OWNER,
            ),
        ]
    )

    project_b = Project(
        organization_id=organization_b.id,
        name="Protected Project",
        slug="protected-project",
    )
    db_session.add(project_b)
    await db_session.flush()

    task_b = Task(
        organization_id=organization_b.id,
        project_id=project_b.id,
        title="Protected Task",
    )
    db_session.add(task_b)
    await db_session.flush()

    project_id = project_b.id
    task_id = task_b.id
    organization_b_id = organization_b.id

    # Intentar modificar el proyecto ajeno.
    with pytest.raises(ProjectNotFoundError):
        await update_project(
            db_session,
            organization_a.id,
            project_id,
            ProjectUpdate(name="Modified Project"),
            user_a,
        )

    # Intentar desactivar el proyecto ajeno.
    with pytest.raises(ProjectNotFoundError):
        await deactivate_project(
            db_session,
            organization_a.id,
            project_id,
            user_a,
        )

    # Intentar modificar la tarea ajena.
    with pytest.raises(TaskNotFoundError):
        await update_task(
            db_session,
            organization_a.id,
            task_id,
            TaskUpdate(title="Modified Task"),
            user_a,
        )

    # Intentar desactivar la tarea ajena.
    with pytest.raises(TaskNotFoundError):
        await deactivate_task(
            db_session,
            organization_a.id,
            task_id,
            user_a,
        )

    await db_session.refresh(project_b)
    await db_session.refresh(task_b)

    assert project_b.name == "Protected Project"
    assert project_b.is_active is True
    assert task_b.title == "Protected Task"
    assert task_b.is_active is True
    assert task_b.organization_id == organization_b_id
