import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationRole
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.schemas.organization import OrganizationCreate


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
