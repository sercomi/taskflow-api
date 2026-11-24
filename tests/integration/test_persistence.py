from app.models.organization import Organization, OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_user_organization_membership_persistence(
    db_session: AsyncSession,
) -> None:
    user = User(
        email="integration@example.com",
        username="integration-user",
        hashed_password="hashed-password",
    )
    organization = Organization(
        name="Integration Organization",
        slug="integration-organization",
    )

    db_session.add_all([user, organization])
    await db_session.flush()

    membership = OrganizationMember(
        organization_id=organization.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
    )
    db_session.add(membership)

    await db_session.commit()

    result = await db_session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization.id,
            OrganizationMember.user_id == user.id,
        )
    )
    persisted_membership = result.scalar_one()

    assert persisted_membership.role == OrganizationRole.OWNER
    assert persisted_membership.organization_id == organization.id
    assert persisted_membership.user_id == user.id

    persisted_user = await db_session.get(User, user.id)
    persisted_organization = await db_session.get(Organization, organization.id)

    assert persisted_user is not None
    assert persisted_user.email == "integration@example.com"

    assert persisted_organization is not None
    assert persisted_organization.slug == "integration-organization"
