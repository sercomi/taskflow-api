from unittest.mock import AsyncMock

import pytest
from app.models.organization import OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.project import Project
from app.models.user import User
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


@pytest.fixture
def sample_project() -> Project:
    return Project(
        id=1,
        organization_id=1,
        name="Backend API",
        slug="backend-api",
        description="Backend project",
        is_active=True,
    )
