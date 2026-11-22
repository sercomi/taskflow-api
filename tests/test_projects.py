from unittest.mock import AsyncMock

import pytest
from app.models.organization import OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.project import ProjectCreate
from app.services import project as project_service
from app.services.project import generate_slug, generate_unique_project_slug
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
