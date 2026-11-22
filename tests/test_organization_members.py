from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.organization import OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.organization_member import OrganizationMemberCreate, OrganizationMemberUpdate
from app.services import organization as organization_service
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
        user_id=1,
        user=current_user,
        role=OrganizationRole.OWNER,
    )


@pytest.fixture
def member_membership() -> OrganizationMember:
    return OrganizationMember(
        organization_id=1,
        user_id=2,
        role=OrganizationRole.MEMBER,
    )


@pytest.mark.asyncio
async def test_remove_member_success(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
    member_membership: OrganizationMember,
) -> None:
    membership_check = AsyncMock(
        return_value=OrganizationMember(
            organization_id=1,
            user_id=1,
            role=OrganizationRole.OWNER,
        )
    )
    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        membership_check,
    )
    mock_session.scalar.return_value = member_membership

    await organization_service.remove_organization_member(
        mock_session,
        1,
        2,
        current_user,
    )

    mock_session.delete.assert_awaited_once_with(member_membership)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_remove_member_rejects_non_admin(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.MEMBER,
    )
    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=membership),
    )

    with pytest.raises(PermissionError):
        await organization_service.remove_organization_member(mock_session, 1, 2, current_user)

    mock_session.delete.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_member_rejects_self_removal(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.OWNER,
    )
    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=membership),
    )

    with pytest.raises(ValueError, match="Cannot remove yourself"):
        await organization_service.remove_organization_member(mock_session, 1, 1, current_user)

    mock_session.delete.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_member_protects_owner(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = OrganizationMember(
        organization_id=1,
        user_id=2,
        role=OrganizationRole.OWNER,
    )
    membership = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.ADMIN,
    )
    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=membership),
    )
    mock_session.scalar.return_value = owner

    with pytest.raises(
        ValueError,
        match="Cannot remove the organization owner",
    ):
        await organization_service.remove_organization_member(mock_session, 1, 2, current_user)

    mock_session.delete.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_member_success(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_membership = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.OWNER,
    )
    new_user = User(
        id=2,
        email="member@example.com",
        username="member",
        hashed_password="hashed-password",
        is_active=True,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = new_user

    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        user_result,
        existing_result,
    ]

    membership = await organization_service.add_organization_member(
        session=mock_session,
        organization_id=1,
        member_data=OrganizationMemberCreate(
            email="member@example.com",
        ),
        current_user=current_user,
    )

    assert membership.user is new_user
    assert membership.role == OrganizationRole.MEMBER
    mock_session.add.assert_called_once_with(membership)
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_member_rejects_insufficient_permissions(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.MEMBER,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=member),
    )

    with pytest.raises(PermissionError):
        await organization_service.add_organization_member(
            session=mock_session,
            organization_id=1,
            member_data=OrganizationMemberCreate(
                email="member@example.com",
            ),
            current_user=current_user,
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_member_rejects_unknown_user(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.OWNER,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner),
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = user_result

    with pytest.raises(LookupError, match="User not found"):
        await organization_service.add_organization_member(
            session=mock_session,
            organization_id=1,
            member_data=OrganizationMemberCreate(
                email="unknown@example.com",
            ),
            current_user=current_user,
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_member_rejects_duplicate(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.OWNER,
    )
    existing_user = User(
        id=2,
        email="member@example.com",
        username="member",
        hashed_password="hashed-password",
        is_active=True,
    )
    existing_membership = OrganizationMember(
        organization_id=1,
        user_id=2,
        role=OrganizationRole.MEMBER,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner),
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = existing_user

    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = existing_membership

    mock_session.execute.side_effect = [
        user_result,
        membership_result,
    ]

    with pytest.raises(ValueError, match="User is already a member"):
        await organization_service.add_organization_member(
            session=mock_session,
            organization_id=1,
            member_data=OrganizationMemberCreate(
                email="member@example.com",
            ),
            current_user=current_user,
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_member_role_success(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_membership = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.OWNER,
    )
    target_user = User(
        id=2,
        email="member@example.com",
        username="member",
        hashed_password="hashed-password",
        is_active=True,
    )
    target_membership = OrganizationMember(
        organization_id=1,
        user_id=2,
        user=target_user,
        role=OrganizationRole.MEMBER,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = target_membership

    result = await organization_service.update_organization_member_role(
        session=mock_session,
        organization_id=1,
        user_id=2,
        member_data=OrganizationMemberUpdate(
            role=OrganizationRole.ADMIN,
        ),
        current_user=current_user,
    )

    assert result is target_membership
    assert result.role == OrganizationRole.ADMIN
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(target_membership)


@pytest.mark.asyncio
async def test_update_member_role_rejects_admin(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_membership = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.ADMIN,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=admin_membership),
    )

    with pytest.raises(PermissionError):
        await organization_service.update_organization_member_role(
            session=mock_session,
            organization_id=1,
            user_id=2,
            member_data=OrganizationMemberUpdate(
                role=OrganizationRole.MEMBER,
            ),
            current_user=current_user,
        )

    mock_session.scalar.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_member_role_rejects_missing_member(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_membership = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.OWNER,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = None

    with pytest.raises(LookupError, match="Member not found"):
        await organization_service.update_organization_member_role(
            session=mock_session,
            organization_id=1,
            user_id=2,
            member_data=OrganizationMemberUpdate(
                role=OrganizationRole.ADMIN,
            ),
            current_user=current_user,
        )

    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_member_role_protects_owner(
    mock_session: AsyncMock,
    current_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_membership = OrganizationMember(
        organization_id=1,
        user_id=1,
        role=OrganizationRole.OWNER,
    )
    target_owner = OrganizationMember(
        organization_id=1,
        user_id=2,
        role=OrganizationRole.OWNER,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )
    mock_session.scalar.return_value = target_owner

    with pytest.raises(
        ValueError,
        match="Cannot change the owner's role",
    ):
        await organization_service.update_organization_member_role(
            session=mock_session,
            organization_id=1,
            user_id=2,
            member_data=OrganizationMemberUpdate(
                role=OrganizationRole.ADMIN,
            ),
            current_user=current_user,
        )

    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_member_handles_concurrent_duplicate(
    mock_session: AsyncMock,
    current_user: User,
    owner_membership: OrganizationMember,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        id=2,
        email="member@example.com",
        username="member",
        hashed_password="hashed-password",
        is_active=True,
    )

    monkeypatch.setattr(
        organization_service,
        "_get_active_organization_membership_for_update",
        AsyncMock(return_value=owner_membership),
    )

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    membership_result = MagicMock()
    membership_result.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        user_result,
        membership_result,
    ]

    original_error = Exception("duplicate key")
    original_error.constraint_name = "uq_organization_member"

    mock_session.commit.side_effect = IntegrityError(
        statement="INSERT INTO organization_members",
        params={},
        orig=original_error,
    )

    with pytest.raises(ValueError, match="User is already a member"):
        await organization_service.add_organization_member(
            session=mock_session,
            organization_id=1,
            member_data=OrganizationMemberCreate(
                email="member@example.com",
            ),
            current_user=current_user,
        )

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()
