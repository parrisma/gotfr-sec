"""Admin-only routes for GOFR token minting."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from gofr_common.auth import VerifiedIdentity

from app.api.dependencies import (
    get_repository_bundle,
    get_service_settings_dependency,
    get_token_signer,
    require_admin_identity,
)
from app.api.schemas.admin_tokens import (
    CreateTokenRequest,
    MintedTokenResponse,
    TokenMetadataResponse,
)
from app.bootstrap import RepositoryBundle
from app.domain.errors import (
    GroupNotFoundError,
    ReservedGroupError,
    SigningKeyUnavailableError,
    TokenNotFoundError,
    UnregisteredUserError,
)
from app.services.token_service import AdminTokenService, TokenSigner
from app.settings import GofrSecServiceSettings

router = APIRouter(tags=["admin"])


def _to_metadata_response(record) -> TokenMetadataResponse:
    return TokenMetadataResponse(
        token_id=record.token_id,
        owner_sub=record.owner_sub,
        granted_groups=list(record.granted_groups),
        status=record.status,
        issued_at=record.issued_at,
        expires_at=record.expires_at,
        revoked_at=record.revoked_at,
        issued_by_sub=record.issued_by_sub,
    )


@router.post(
    "/v1/users/{keycloak_sub}/tokens",
    response_model=MintedTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Mint GOFR runtime token",
    description=(
        "Admin-only endpoint. Requires a verified Keycloak bearer token whose "
        "subject already belongs to the reserved admin group in gofr-sec. "
        "Returns the raw JWT only at mint time while storing canonical token "
        "metadata in gofr-sec storage."
    ),
)
async def create_token(
    keycloak_sub: str,
    payload: CreateTokenRequest,
    request: Request,
    admin_identity: VerifiedIdentity = Depends(require_admin_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
    settings: GofrSecServiceSettings = Depends(get_service_settings_dependency),
    token_signer: TokenSigner = Depends(get_token_signer),
) -> MintedTokenResponse:
    service = AdminTokenService(
        bundle.groups,
        bundle.user_profiles,
        bundle.tokens,
        bundle.audit,
        token_signer,
        default_lifetime_seconds=settings.signing.default_lifetime_seconds,
    )
    correlation_id = request.headers.get("X-Correlation-ID")

    try:
        minted = service.mint_token(
            owner_sub=keycloak_sub,
            groups=payload.groups,
            actor_sub=admin_identity.subject,
            correlation_id=correlation_id,
            expires_in_seconds=payload.expires_in_seconds,
        )
    except UnregisteredUserError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GroupNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ReservedGroupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except SigningKeyUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return MintedTokenResponse(
        **_to_metadata_response(minted.record).model_dump(),
        issued_token=minted.raw_token,
    )


@router.get(
    "/v1/tokens/{token_id}",
    response_model=TokenMetadataResponse,
    summary="Inspect GOFR runtime token metadata",
    description=(
        "Admin-only endpoint. Requires a verified Keycloak bearer token whose "
        "subject already belongs to the reserved admin group in gofr-sec. "
        "Returns canonical token metadata without revealing the raw JWT."
    ),
)
async def get_token(
    token_id: str,
    request: Request,
    admin_identity: VerifiedIdentity = Depends(require_admin_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> TokenMetadataResponse:
    service = AdminTokenService(
        bundle.groups,
        bundle.user_profiles,
        bundle.tokens,
        bundle.audit,
        token_signer=_NoopTokenSigner(),
    )
    correlation_id = request.headers.get("X-Correlation-ID")

    try:
        record = service.get_token(
            token_id=token_id,
            actor_sub=admin_identity.subject,
            correlation_id=correlation_id,
        )
    except TokenNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _to_metadata_response(record)


@router.post(
    "/v1/tokens/{token_id}/revoke",
    response_model=TokenMetadataResponse,
    summary="Revoke GOFR runtime token",
    description=(
        "Admin-only endpoint. Requires a verified Keycloak bearer token whose "
        "subject already belongs to the reserved admin group in gofr-sec. "
        "Marks the canonical token record revoked without revealing the raw JWT."
    ),
)
async def revoke_token(
    token_id: str,
    request: Request,
    admin_identity: VerifiedIdentity = Depends(require_admin_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> TokenMetadataResponse:
    service = AdminTokenService(
        bundle.groups,
        bundle.user_profiles,
        bundle.tokens,
        bundle.audit,
        token_signer=_NoopTokenSigner(),
    )
    correlation_id = request.headers.get("X-Correlation-ID")

    try:
        record = service.revoke_token(
            token_id=token_id,
            actor_sub=admin_identity.subject,
            correlation_id=correlation_id,
        )
    except TokenNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _to_metadata_response(record)


class _NoopTokenSigner:
    def sign_token(self, **kwargs):
        raise RuntimeError("sign_token should not be called for inspect or revoke")

    def public_key_pem(self) -> str:
        raise RuntimeError("public_key_pem is not used for inspect or revoke")