import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate
from app.services.organization import (
    _get_active_organization_membership_for_update,
)


def generate_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower())
    return slug.strip("-")


async def generate_unique_project_slug(
    session: AsyncSession,
    organization_id: int,
    name: str,
) -> str:
    base_slug = generate_slug(name)

    if not base_slug:
        base_slug = "project"

    slug = base_slug
    suffix = 2

    while await session.scalar(
        select(Project.id).where(
            Project.organization_id == organization_id,
            Project.slug == slug,
        )
    ):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    return slug


async def create_project(
    session: AsyncSession,
    organization_id: int,
    project_data: ProjectCreate,
    current_user: User,
) -> Project:
    membership = await _get_active_organization_membership_for_update(
        session=session,
        organization_id=organization_id,
        user_id=current_user.id,
    )

    if membership is None:
        raise LookupError("Organization not found")

    slug = await generate_unique_project_slug(
        session=session,
        organization_id=organization_id,
        name=project_data.name,
    )

    project = Project(
        organization_id=organization_id,
        name=project_data.name,
        slug=slug,
        description=project_data.description,
    )

    session.add(project)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise

    await session.refresh(project)

    return project
