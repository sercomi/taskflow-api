import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.exceptions import (
    OrganizationNotFoundError,
    ProjectNotFoundError,
)
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
    exclude_project_id: int | None = None,
) -> str:
    base_slug = generate_slug(name)

    if not base_slug:
        base_slug = "project"

    slug = base_slug
    suffix = 2

    while True:
        query = select(Project.id).where(
            Project.organization_id == organization_id,
            Project.slug == slug,
        )

        if exclude_project_id is not None:
            query = query.where(Project.id != exclude_project_id)

        if await session.scalar(query) is None:
            return slug

        slug = f"{base_slug}-{suffix}"
        suffix += 1


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
        raise OrganizationNotFoundError("Organization not found")

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


async def get_organization_projects(
    session: AsyncSession,
    organization_id: int,
    current_user: User,
) -> list[Project]:
    membership = await session.scalar(
        select(OrganizationMember.id)
        .join(
            Organization,
            Organization.id == OrganizationMember.organization_id,
        )
        .where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == current_user.id,
            Organization.is_active.is_(True),
        )
    )

    if membership is None:
        raise OrganizationNotFoundError("Organization not found")

    result = await session.scalars(
        select(Project)
        .where(
            Project.organization_id == organization_id,
            Project.is_active.is_(True),
        )
        .order_by(Project.created_at.desc())
    )

    return list(result.all())


async def get_project_by_id(
    session: AsyncSession,
    organization_id: int,
    project_id: int,
    current_user: User,
) -> Project:
    project = await session.scalar(
        select(Project)
        .join(
            OrganizationMember,
            OrganizationMember.organization_id == Project.organization_id,
        )
        .join(
            Organization,
            Organization.id == OrganizationMember.organization_id,
        )
        .where(
            Project.id == project_id,
            Project.organization_id == organization_id,
            Project.is_active.is_(True),
            Organization.is_active.is_(True),
            OrganizationMember.user_id == current_user.id,
        )
    )

    if project is None:
        raise ProjectNotFoundError("Project not found")

    return project


async def update_project(
    session: AsyncSession,
    organization_id: int,
    project_id: int,
    project_data: ProjectUpdate,
    current_user: User,
) -> Project:
    membership = await _get_active_organization_membership_for_update(
        session,
        organization_id,
        current_user.id,
    )

    if membership is None:
        raise OrganizationNotFoundError("Organization not found")

    project = await session.scalar(
        select(Project)
        .where(
            Project.id == project_id,
            Project.organization_id == organization_id,
            Project.is_active.is_(True),
        )
        .with_for_update()
    )

    if project is None:
        raise ProjectNotFoundError("Project not found")

    update_data = project_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        new_name = update_data["name"]

        if new_name != project.name:
            project.name = new_name
            project.slug = await generate_unique_project_slug(
                session,
                organization_id,
                new_name,
                exclude_project_id=project.id,
            )

    if "description" in update_data:
        project.description = update_data["description"]

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise

    await session.refresh(project)

    return project


async def deactivate_project(
    session: AsyncSession,
    organization_id: int,
    project_id: int,
    current_user: User,
) -> None:
    membership = await _get_active_organization_membership_for_update(
        session,
        organization_id,
        current_user.id,
    )

    if membership is None:
        raise OrganizationNotFoundError("Organization not found")

    project = await session.scalar(
        select(Project)
        .where(
            Project.id == project_id,
            Project.organization_id == organization_id,
            Project.is_active.is_(True),
        )
        .with_for_update()
    )

    if project is None:
        raise ProjectNotFoundError("Project not found")

    project.is_active = False

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
