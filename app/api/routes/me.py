"""Self-service routes for local registration and profile reads."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from gofr_common.auth import VerifiedIdentity

from app.api.dependencies import get_repository_bundle, get_verified_identity
from app.api.schemas.me import MeProfileResponse, MeRegisterResponse
from app.bootstrap import RepositoryBundle
from app.services.user_registration_service import UserRegistrationService

router = APIRouter(tags=["me"])


@router.post(
    "/v1/me/register",
    response_model=MeRegisterResponse,
    summary="Register current Keycloak user",
    description=(
        "Requires a verified Keycloak bearer token. Creates or refreshes the "
        "local GOFR user profile for the caller subject without granting groups or tokens."
    ),
)
async def register_me(
    request: Request,
    identity: VerifiedIdentity = Depends(get_verified_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> MeRegisterResponse:
    service = UserRegistrationService(
        bundle.user_profiles,
        bundle.memberships,
        bundle.audit,
    )
    correlation_id = request.headers.get("X-Correlation-ID")
    result = service.register_self(identity, correlation_id=correlation_id)

    return MeRegisterResponse(
        keycloak_sub=result.profile.keycloak_sub,
        display_name=result.profile.display_name,
        email=result.profile.email,
        registered_at=result.profile.registered_at,
        updated_at=result.profile.updated_at,
        registration_status=result.registration_status,
    )


@router.get(
    "/v1/me",
    response_model=MeProfileResponse,
    summary="Read current GOFR profile",
    description=(
        "Requires a verified Keycloak bearer token. Returns the caller's local "
        "registration state and current GOFR group memberships without creating a profile."
    ),
)
async def get_me(
    identity: VerifiedIdentity = Depends(get_verified_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> MeProfileResponse:
    service = UserRegistrationService(
        bundle.user_profiles,
        bundle.memberships,
        bundle.audit,
    )
    profile_view = service.get_self_profile(identity)

    return MeProfileResponse(
        keycloak_sub=profile_view.keycloak_sub,
        is_registered=profile_view.is_registered,
        display_name=profile_view.display_name,
        email=profile_view.email,
        registered_at=profile_view.registered_at,
        updated_at=profile_view.updated_at,
        groups=list(profile_view.groups),
    )