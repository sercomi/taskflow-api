from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.project import ProjectResponse, ProjectUpdate
from app.services.project import (
    deactivate_project,
    get_organization_projects,
    get_project_by_id,
    update_project,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/projects",
    tags=["Projects"],
)


@router.get(
    "",
    response_model=list[ProjectResponse],
)
async def list_projects_endpoint(
    organization_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProjectResponse]:
    try:
        projects = await get_organization_projects(
            session=session,
            organization_id=organization_id,
            current_user=current_user,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None

    return [ProjectResponse.model_validate(project) for project in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
)
async def get_project_endpoint(
    organization_id: int,
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectResponse:
    try:
        project = await get_project_by_id(
            session=session,
            organization_id=organization_id,
            project_id=project_id,
            current_user=current_user,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from None

    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_endpoint(
    organization_id: int,
    project_id: int,
    project_data: ProjectUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProjectResponse:
    try:
        project = await update_project(
            session=session,
            organization_id=organization_id,
            project_id=project_id,
            project_data=project_data,
            current_user=current_user,
        )
    except LookupError as exc:
        if str(exc) == "Organization not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            ) from None

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from None

    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_project_endpoint(
    organization_id: int,
    project_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        await deactivate_project(
            session=session,
            organization_id=organization_id,
            project_id=project_id,
            current_user=current_user,
        )
    except LookupError as exc:
        if str(exc) == "Organization not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            ) from None

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from None
