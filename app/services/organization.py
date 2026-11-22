import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.organization import Organization, OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.organization import OrganizationCreate
from app.schemas.organization_member import OrganizationMemberCreate, OrganizationMemberUpdate


def generate_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower())
    return slug.strip("-")


async def generate_unique_slug(
    session: AsyncSession,
    name: str,
) -> str:
    base_slug = generate_slug(name)

    if not base_slug:
        base_slug = "organization"

    slug = base_slug
    suffix = 2

    while await session.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    return slug


async def create_organization(
    session: AsyncSession,
    organization_data: OrganizationCreate,
    user: User,
) -> Organization:
    slug = await generate_unique_slug(session, organization_data.name)

    organization = Organization(
        name=organization_data.name,
        slug=slug,
        description=organization_data.description,
    )

    membership = OrganizationMember(
        organization=organization,
        user=user,
        role=OrganizationRole.OWNER,
    )

    session.add(organization)
    session.add(membership)

    await session.commit()
    await session.refresh(organization)

    return organization


async def get_user_organizations(
    session: AsyncSession,
    user: User,
) -> list[Organization]:
    result = await session.scalars(
        select(Organization)
        .join(OrganizationMember)
        .where(
            OrganizationMember.user_id == user.id,
            Organization.is_active.is_(True),
        )
        .order_by(Organization.name)
    )

    return list(result.all())


async def get_user_organization(
    session: AsyncSession,
    organization_id: int,
    user: User,
) -> Organization | None:
    result = await session.execute(
        select(Organization)
        .join(OrganizationMember)
        .where(
            Organization.id == organization_id,
            OrganizationMember.user_id == user.id,
            Organization.is_active.is_(True),
        )
    )

    return result.scalar_one_or_none()


async def _get_active_organization_membership(
    session: AsyncSession,
    organization_id: int,
    user_id: int,
) -> OrganizationMember | None:
    result = await session.execute(
        select(OrganizationMember)
        .join(Organization)
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
            Organization.is_active.is_(True),
        )
    )

    return result.scalar_one_or_none()


async def _get_active_organization_membership_for_update(
    session: AsyncSession,
    organization_id: int,
    user_id: int,
) -> OrganizationMember | None:
    result = await session.execute(
        select(OrganizationMember)
        .join(Organization)
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
            Organization.is_active.is_(True),
        )
        .with_for_update(of=OrganizationMember)
    )

    return result.scalar_one_or_none()


async def get_organization_members(
    session: AsyncSession,
    organization_id: int,
    current_user: User,
) -> list[OrganizationMember]:
    current_membership = await _get_active_organization_membership(
        session=session,
        organization_id=organization_id,
        user_id=current_user.id,
    )

    if current_membership is None:
        raise LookupError("Organization not found")

    result = await session.scalars(
        select(OrganizationMember)
        .join(Organization)
        .options(selectinload(OrganizationMember.user))
        .where(
            OrganizationMember.organization_id == organization_id,
            Organization.is_active.is_(True),
        )
        .order_by(User.email)
        .join(User)
    )

    return list(result.all())


async def add_organization_member(
    session: AsyncSession,
    organization_id: int,
    member_data: OrganizationMemberCreate,
    current_user: User,
) -> OrganizationMember:
    current_membership = await _get_active_organization_membership_for_update(
        session=session,
        organization_id=organization_id,
        user_id=current_user.id,
    )

    if current_membership is None:
        raise LookupError("Organization not found")

    if current_membership.role not in {
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
    }:
        raise PermissionError("Insufficient permissions")

    result = await session.execute(select(User).where(User.email == str(member_data.email).lower()))
    user = result.scalar_one_or_none()

    if user is None:
        raise LookupError("User not found")

    existing_membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )

    if existing_membership.scalar_one_or_none() is not None:
        raise ValueError("User is already a member")

    membership = OrganizationMember(
        organization_id=organization_id,
        user=user,
        role=OrganizationRole.MEMBER,
    )

    session.add(membership)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()

        constraint_name = getattr(exc.orig, "constraint_name", None)

        if constraint_name == "uq_organization_member":
            raise ValueError("User is already a member") from exc

        raise

    return membership


async def update_organization_member_role(
    session: AsyncSession,
    organization_id: int,
    user_id: int,
    member_data: OrganizationMemberUpdate,
    current_user: User,
) -> OrganizationMember:
    current_membership = await _get_active_organization_membership_for_update(
        session=session,
        organization_id=organization_id,
        user_id=current_user.id,
    )

    if current_membership is None:
        raise LookupError("Organization not found")

    if current_membership.role != OrganizationRole.OWNER:
        raise PermissionError("Only the owner can update member roles")

    target_membership = await session.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
        .with_for_update()
    )

    if target_membership is None:
        raise LookupError("Member not found")

    if target_membership.role == OrganizationRole.OWNER:
        raise ValueError("Cannot change the owner's role")

    target_membership.role = member_data.role

    await session.commit()
    await session.refresh(target_membership)

    return target_membership


async def remove_organization_member(
    session: AsyncSession,
    organization_id: int,
    user_id: int,
    current_user: User,
) -> None:
    current_membership = await _get_active_organization_membership_for_update(
        session=session,
        organization_id=organization_id,
        user_id=current_user.id,
    )

    if current_membership is None:
        raise LookupError("Organization not found")

    if current_membership.role not in {
        OrganizationRole.OWNER,
        OrganizationRole.ADMIN,
    }:
        raise PermissionError("Insufficient permissions")

    if user_id == current_user.id:
        raise ValueError("Cannot remove yourself")

    target_membership = await session.scalar(
        select(OrganizationMember)
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
        .with_for_update()
    )

    if target_membership is None:
        raise LookupError("Member not found")

    if target_membership.role == OrganizationRole.OWNER:
        raise ValueError("Cannot remove the organization owner")

    await session.delete(target_membership)
    await session.commit()
