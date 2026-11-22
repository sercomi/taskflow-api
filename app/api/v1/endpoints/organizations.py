from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.services.organization import create_organization

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_endpoint(
    organization_data: OrganizationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationResponse:
    try:
        organization = await create_organization(
            session=session,
            organization_data=organization_data,
            user=current_user,
        )
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create organization",
        ) from None

    return OrganizationResponse.model_validate(organization)
