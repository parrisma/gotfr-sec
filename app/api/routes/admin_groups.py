"""Admin-only routes for GOFR group management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from gofr_common.auth import VerifiedIdentity

from app.api.dependencies import get_repository_bundle, require_admin_identity
from app.api.schemas.admin_groups import CreateGroupRequest, GroupResponse
from app.bootstrap import RepositoryBundle
from app.domain.errors import GroupAlreadyExistsError, ReservedGroupError
from app.services.admin_group_service import AdminGroupService

router = APIRouter(tags=["admin"])


@router.post(
    "/v1/groups",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create GOFR group",
    description=(
        "Admin-only endpoint. Requires a verified Keycloak bearer token whose "
        "subject already belongs to the reserved admin group in gofr-sec."
    ),
)
async def create_group(
    payload: CreateGroupRequest,
    request: Request,
    admin_identity: VerifiedIdentity = Depends(require_admin_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> GroupResponse:
    service = AdminGroupService(
        bundle.groups,
        bundle.memberships,
        bundle.user_profiles,
        bundle.audit,
    )
    correlation_id = request.headers.get("X-Correlation-ID")

    try:
        group = service.create_group(
            name=payload.name,
            description=payload.description,
            actor_sub=admin_identity.subject,
            correlation_id=correlation_id,
        )
    except GroupAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ReservedGroupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return GroupResponse(
        name=group.name,
        description=group.description,
        is_system=group.is_system,
        is_active=group.is_active,
        created_at=group.created_at,
    )