"""Admin-only routes for GOFR membership management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from gofr_common.auth import VerifiedIdentity

from app.api.dependencies import get_repository_bundle, require_admin_identity
from app.api.schemas.admin_memberships import GroupMembershipResponse
from app.bootstrap import RepositoryBundle
from app.domain.errors import (
    GroupMembershipNotFoundError,
    GroupNotFoundError,
    LastAdminRemovalError,
    UnregisteredUserError,
)
from app.services.admin_group_service import AdminGroupService

router = APIRouter(tags=["admin"])


@router.post(
    "/v1/users/{keycloak_sub}/groups/{group}",
    response_model=GroupMembershipResponse,
    summary="Add user to GOFR group",
    description=(
        "Admin-only endpoint. Requires a verified Keycloak bearer token for a "
        "local admin subject and a pre-registered target user."
    ),
)
async def add_group_membership(
    keycloak_sub: str,
    group: str,
    request: Request,
    admin_identity: VerifiedIdentity = Depends(require_admin_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> GroupMembershipResponse:
    service = AdminGroupService(
        bundle.groups,
        bundle.memberships,
        bundle.user_profiles,
        bundle.audit,
    )
    correlation_id = request.headers.get("X-Correlation-ID")

    try:
        membership = service.add_membership(
            keycloak_sub=keycloak_sub,
            group_name=group,
            actor_sub=admin_identity.subject,
            correlation_id=correlation_id,
        )
    except GroupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnregisteredUserError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return GroupMembershipResponse(
        keycloak_sub=membership.keycloak_sub,
        group_name=membership.group_name,
        granted_at=membership.granted_at,
        granted_by_sub=membership.granted_by_sub,
    )


@router.delete(
    "/v1/users/{keycloak_sub}/groups/{group}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remove user from GOFR group",
    description=(
        "Admin-only endpoint. Requires a verified Keycloak bearer token for a "
        "local admin subject and enforces the last-admin protection rule."
    ),
)
async def remove_group_membership(
    keycloak_sub: str,
    group: str,
    request: Request,
    admin_identity: VerifiedIdentity = Depends(require_admin_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> Response:
    service = AdminGroupService(
        bundle.groups,
        bundle.memberships,
        bundle.user_profiles,
        bundle.audit,
    )
    correlation_id = request.headers.get("X-Correlation-ID")

    try:
        service.remove_membership(
            keycloak_sub=keycloak_sub,
            group_name=group,
            actor_sub=admin_identity.subject,
            correlation_id=correlation_id,
        )
    except GroupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GroupMembershipNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UnregisteredUserError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except LastAdminRemovalError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)