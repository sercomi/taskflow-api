from collections.abc import Callable

import httpx2
import pytest
from app.models.organization import Organization, OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_user_cannot_access_other_organizations_projects(
    api_client: httpx2.AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user_a = User(
        email="user-a@example.com",
        username="user_a",
        hashed_password="hashed-password",
        is_active=True,
    )
    user_b = User(
        email="user-b@example.com",
        username="user_b",
        hashed_password="hashed-password",
        is_active=True,
    )

    organization_a = Organization(name="Organization A", slug="organization-a")
    organization_b = Organization(name="Organization B", slug="organization-b")

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

    db_session.add_all([project_a, project_b])
    await db_session.flush()

    headers = auth_headers(user_a)

    own_response = await api_client.get(
        f"/api/v1/organizations/{organization_a.id}/projects",
        headers=headers,
    )

    foreign_response = await api_client.get(
        f"/api/v1/organizations/{organization_b.id}/projects",
        headers=headers,
    )

    assert own_response.status_code == 200
    assert len(own_response.json()) == 1
    assert own_response.json()[0]["id"] == project_a.id

    assert foreign_response.status_code == 404
    assert foreign_response.json()["detail"] == "Organization not found"


@pytest.mark.asyncio
async def test_user_cannot_access_other_organizations_tasks(
    api_client: httpx2.AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user_a = User(
        email="task-user-a@example.com",
        username="task_user_a",
        hashed_password="hashed-password",
        is_active=True,
    )
    user_b = User(
        email="task-user-b@example.com",
        username="task_user_b",
        hashed_password="hashed-password",
        is_active=True,
    )

    organization_a = Organization(name="Task Organization A", slug="task-organization-a")
    organization_b = Organization(name="Task Organization B", slug="task-organization-b")

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

    project_a = Project(
        organization_id=organization_a.id,
        name="Task Project A",
        slug="task-project-a",
    )
    project_b = Project(
        organization_id=organization_b.id,
        name="Task Project B",
        slug="task-project-b",
    )

    db_session.add_all([project_a, project_b])
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

    headers = auth_headers(user_a)

    own_tasks_response = await api_client.get(
        f"/api/v1/organizations/{organization_a.id}/projects/{project_a.id}/tasks",
        headers=headers,
    )

    foreign_project_response = await api_client.get(
        f"/api/v1/organizations/{organization_a.id}/projects/{project_b.id}/tasks",
        headers=headers,
    )

    foreign_task_response = await api_client.get(
        f"/api/v1/organizations/{organization_a.id}/tasks/{task_b.id}",
        headers=headers,
    )

    assert own_tasks_response.status_code == 200
    assert len(own_tasks_response.json()) == 1
    assert own_tasks_response.json()[0]["id"] == task_a.id

    assert foreign_project_response.status_code == 404
    assert foreign_project_response.json()["detail"] == "Project not found"

    assert foreign_task_response.status_code == 404
    assert foreign_task_response.json()["detail"] == "Task not found"


@pytest.mark.asyncio
async def test_user_cannot_modify_other_organizations_resources(
    api_client: httpx2.AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user_a = User(
        email="write-user-a@example.com",
        username="write_user_a",
        hashed_password="hashed-password",
        is_active=True,
    )
    user_b = User(
        email="write-user-b@example.com",
        username="write_user_b",
        hashed_password="hashed-password",
        is_active=True,
    )

    organization_a = Organization(name="Write Organization A", slug="write-organization-a")
    organization_b = Organization(name="Write Organization B", slug="write-organization-b")

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

    headers = auth_headers(user_a)

    project_patch_response = await api_client.patch(
        f"/api/v1/organizations/{organization_a.id}/projects/{project_b.id}",
        headers=headers,
        json={"name": "Modified project"},
    )

    project_delete_response = await api_client.delete(
        f"/api/v1/organizations/{organization_a.id}/projects/{project_b.id}",
        headers=headers,
    )

    task_patch_response = await api_client.patch(
        f"/api/v1/organizations/{organization_a.id}/tasks/{task_b.id}",
        headers=headers,
        json={"title": "Modified task"},
    )

    task_delete_response = await api_client.delete(
        f"/api/v1/organizations/{organization_a.id}/tasks/{task_b.id}",
        headers=headers,
    )

    assert project_patch_response.status_code == 404
    assert project_patch_response.json()["detail"] == "Project not found"

    assert project_delete_response.status_code == 404
    assert project_delete_response.json()["detail"] == "Project not found"

    assert task_patch_response.status_code == 404
    assert task_patch_response.json()["detail"] == "Task not found"

    assert task_delete_response.status_code == 404
    assert task_delete_response.json()["detail"] == "Task not found"

    await db_session.refresh(project_b)
    await db_session.refresh(task_b)

    assert project_b.name == "Protected Project"
    assert project_b.is_active is True

    assert task_b.title == "Protected Task"
    assert task_b.is_active is True


@pytest.mark.asyncio
async def test_inactive_user_cannot_access_api_with_valid_token(
    api_client: httpx2.AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user = User(
        email="inactive-user@example.com",
        username="inactive_user",
        hashed_password="hashed-password",
        is_active=False,
    )
    organization = Organization(
        name="Inactive Organization",
        slug="inactive-organization",
    )

    db_session.add_all([user, organization])
    await db_session.flush()

    db_session.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.OWNER,
        )
    )

    project = Project(
        organization_id=organization.id,
        name="Inactive Project",
        slug="inactive-project",
    )
    db_session.add(project)
    await db_session.flush()

    headers = auth_headers(user)

    response = await api_client.get(
        f"/api/v1/organizations/{organization.id}/projects",
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user"


@pytest.mark.asyncio
async def test_user_loses_access_after_membership_removal(
    api_client: httpx2.AsyncClient,
    db_session: AsyncSession,
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    user = User(
        email="revoked-user@example.com",
        username="revoked_user",
        hashed_password="hashed-password",
        is_active=True,
    )
    organization = Organization(
        name="Revoked Organization",
        slug="revoked-organization",
    )

    db_session.add_all([user, organization])
    await db_session.flush()

    membership = OrganizationMember(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
    )
    db_session.add(membership)

    project = Project(
        organization_id=organization.id,
        name="Revoked Project",
        slug="revoked-project",
    )
    db_session.add(project)
    await db_session.flush()

    headers = auth_headers(user)
    url = f"/api/v1/organizations/{organization.id}/projects"

    initial_response = await api_client.get(url, headers=headers)

    assert initial_response.status_code == 200
    assert len(initial_response.json()) == 1

    await db_session.delete(membership)
    await db_session.flush()

    revoked_response = await api_client.get(url, headers=headers)

    assert revoked_response.status_code == 404
    assert revoked_response.json()["detail"] == "Organization not found"
