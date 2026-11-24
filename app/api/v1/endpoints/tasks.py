from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.task import TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.exceptions import (
    OrganizationNotFoundError,
    ProjectNotFoundError,
    TaskAssigneeNotFoundError,
    TaskNotFoundError,
)
from app.services.task import (
    create_task,
    deactivate_task,
    get_project_tasks,
    get_task_by_id,
    update_task,
)

router = APIRouter(
    prefix="/organizations/{organization_id}",
    tags=["Tasks"],
)


@router.get(
    "/projects/{project_id}/tasks",
    response_model=list[TaskResponse],
)
async def list_project_tasks(
    organization_id: Annotated[int, Path(gt=0)],
    project_id: Annotated[int, Path(gt=0)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: TaskPriority | None = None,
    assignee_id: Annotated[int | None, Query(gt=0)] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
) -> list[TaskResponse]:
    try:
        tasks = await get_project_tasks(
            session=session,
            organization_id=organization_id,
            project_id=project_id,
            current_user=current_user,
            status=status_filter,
            priority=priority,
            assignee_id=assignee_id,
            search=search,
        )
        return [TaskResponse.model_validate(task) for task in tasks]
    except OrganizationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
)
async def get_task_endpoint(
    organization_id: Annotated[int, Path(gt=0)],
    task_id: Annotated[int, Path(gt=0)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskResponse:
    try:
        task = await get_task_by_id(
            session=session,
            organization_id=organization_id,
            task_id=task_id,
            current_user=current_user,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from None

    return TaskResponse.model_validate(task)


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_endpoint(
    organization_id: Annotated[int, Path(gt=0)],
    task_data: TaskCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskResponse:
    try:
        task = await create_task(
            session=session,
            organization_id=organization_id,
            task_data=task_data,
            current_user=current_user,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None
    except ProjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        ) from None
    except TaskAssigneeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task assignee not found",
        ) from None
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task could not be created",
        ) from None

    return TaskResponse.model_validate(task)


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
)
async def update_task_endpoint(
    organization_id: Annotated[int, Path(gt=0)],
    task_id: Annotated[int, Path(gt=0)],
    task_data: TaskUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TaskResponse:
    try:
        task = await update_task(
            session=session,
            organization_id=organization_id,
            task_id=task_id,
            task_data=task_data,
            current_user=current_user,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from None
    except TaskAssigneeNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task assignee not found",
        ) from None
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task could not be updated",
        ) from None

    return TaskResponse.model_validate(task)


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_task_endpoint(
    organization_id: Annotated[int, Path(gt=0)],
    task_id: Annotated[int, Path(gt=0)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        await deactivate_task(
            session=session,
            organization_id=organization_id,
            task_id=task_id,
            current_user=current_user,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from None
