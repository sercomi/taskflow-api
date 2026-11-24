from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models.user import User
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.schemas.organization_member import (
    OrganizationMemberCreate,
    OrganizationMemberResponse,
    OrganizationMemberUpdate,
)
from app.services.exceptions import (
    DuplicateOrganizationMemberError,
    MemberNotFoundError,
    OrganizationNotFoundError,
    OrganizationOwnerError,
    SelfRemovalError,
    UserNotFoundError,
)
from app.services.organization import (
    add_organization_member,
    create_organization,
    get_organization_members,
    get_user_organization,
    get_user_organizations,
    remove_organization_member,
    update_organization_member_role,
)

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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create organization",
        ) from None

    return OrganizationResponse.model_validate(organization)


@router.get(
    "",
    response_model=list[OrganizationResponse],
)
async def list_organizations_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[OrganizationResponse]:
    organizations = await get_user_organizations(
        session=session,
        user=current_user,
    )

    return [OrganizationResponse.model_validate(organization) for organization in organizations]


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
)
async def get_organization_endpoint(
    organization_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationResponse:
    organization = await get_user_organization(
        session=session,
        organization_id=organization_id,
        user=current_user,
    )

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return OrganizationResponse.model_validate(organization)


@router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMemberResponse],
)
async def list_organization_members_endpoint(
    organization_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[OrganizationMemberResponse]:
    try:
        members = await get_organization_members(
            session=session,
            organization_id=organization_id,
            current_user=current_user,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None

    return [
        OrganizationMemberResponse(
            user_id=member.user.id,
            email=member.user.email,
            username=member.user.username,
            role=member.role,
        )
        for member in members
    ]


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_organization_member_endpoint(
    organization_id: int,
    member_data: OrganizationMemberCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationMemberResponse:
    try:
        membership = await add_organization_member(
            session=session,
            organization_id=organization_id,
            member_data=member_data,
            current_user=current_user,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from None
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except DuplicateOrganizationMemberError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member",
        ) from None

    return OrganizationMemberResponse(
        user_id=membership.user.id,
        email=membership.user.email,
        username=membership.user.username,
        role=membership.role,
    )


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=OrganizationMemberResponse,
)
async def update_organization_member_endpoint(
    organization_id: int,
    user_id: int,
    member_data: OrganizationMemberUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OrganizationMemberResponse:
    try:
        membership = await update_organization_member_role(
            session=session,
            organization_id=organization_id,
            user_id=user_id,
            member_data=member_data,
            current_user=current_user,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None
    except MemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        ) from None
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except OrganizationOwnerError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot change the owner's role",
        ) from None

    return OrganizationMemberResponse(
        user_id=membership.user.id,
        email=membership.user.email,
        username=membership.user.username,
        role=membership.role,
    )


@router.delete(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_organization_member_endpoint(
    organization_id: int,
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        await remove_organization_member(
            session=session,
            organization_id=organization_id,
            user_id=user_id,
            current_user=current_user,
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        ) from None
    except MemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        ) from None
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        ) from None
    except SelfRemovalError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove yourself",
        ) from None
    except OrganizationOwnerError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove the organization owner",
        ) from None
