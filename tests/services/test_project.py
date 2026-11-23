from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.organization_member import OrganizationMember
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services import project as project_service
from app.services.exceptions import OrganizationNotFoundError, ProjectNotFoundError
from app.services.project import (
    generate_slug,
    generate_unique_project_slug,
    update_project,
)
from sqlalchemy.exc import IntegrityError


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

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
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

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
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

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
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

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
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

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
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

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
        await project_service.get_project_by_id(
            session=mock_session,
            organization_id=1,
            project_id=1,
            current_user=current_user,
        )


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

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
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

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
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


@pytest.mark.asyncio
async def test_update_project_name_with_same_normalized_slug(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    sample_project: Project,
) -> None:
    sample_project.name = "Backend API"
    sample_project.slug = "backend-api"

    mock_session.scalar.side_effect = [
        sample_project,
        None,
    ]

    project_data = ProjectUpdate(name="Backend-API")

    with patch(
        "app.services.project._get_active_organization_membership_for_update",
        new_callable=AsyncMock,
        return_value=owner_membership,
    ):
        result = await update_project(
            session=mock_session,
            organization_id=sample_project.organization_id,
            project_id=sample_project.id,
            project_data=project_data,
            current_user=current_user,
        )

    assert result.name == "Backend-API"
    assert result.slug == "backend-api"
    mock_session.commit.assert_awaited_once()


async def test_deactivate_project_success(
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

    await project_service.deactivate_project(
        mock_session,
        1,
        1,
        current_user,
    )

    assert sample_project.is_active is False
    mock_session.commit.assert_awaited_once()


async def test_deactivate_project_rejects_non_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        project_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=None),
    )

    with pytest.raises(OrganizationNotFoundError, match="Organization not found"):
        await project_service.deactivate_project(
            mock_session,
            1,
            1,
            current_user,
        )

    mock_session.scalar.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


async def test_deactivate_project_not_found(
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

    with pytest.raises(ProjectNotFoundError, match="Project not found"):
        await project_service.deactivate_project(
            mock_session,
            1,
            999,
            current_user,
        )

    mock_session.commit.assert_not_awaited()


async def test_deactivate_project_rolls_back_on_integrity_error(
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
    mock_session.commit.side_effect = IntegrityError(
        "UPDATE",
        {},
        Exception("database error"),
    )

    with pytest.raises(IntegrityError):
        await project_service.deactivate_project(
            mock_session,
            1,
            1,
            current_user,
        )

    mock_session.rollback.assert_awaited_once()
