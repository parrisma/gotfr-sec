"""Routes for the GOFR runtime verification and authorization contract."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_repository_bundle, get_token_signer
from app.api.schemas.runtime import (
    RuntimeAuthorizationRequestSchema,
    RuntimeAuthorizationResponse,
)
from app.bootstrap import RepositoryBundle
from app.domain.models import AuthorizationRequest
from app.services.runtime_service import RuntimeAuthorizationService
from app.services.token_service import TokenSigner

router = APIRouter(tags=["runtime"])


@router.get(
    "/v1/runtime/keys/public",
    summary="Read runtime verification keys",
    description=(
        "Returns the public verification key set that GOFR services use for "
        "local verification of gofr-sec runtime tokens."
    ),
)
async def get_runtime_public_keys(
    token_signer: TokenSigner = Depends(get_token_signer),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> dict[str, object]:
    service = RuntimeAuthorizationService(bundle.tokens, bundle.audit)
    return service.get_public_key_document(token_signer)


@router.post(
    "/v1/runtime/authorize",
    response_model=RuntimeAuthorizationResponse,
    summary="Authorize runtime token access",
    description=(
        "Returns only yes or no for a verified runtime token id, owner subject, "
        "and requested group or resource. Denials are normalized and do not "
        "reveal token status, ownership mismatches, or resource existence."
    ),
)
async def authorize_runtime_request(
    payload: RuntimeAuthorizationRequestSchema,
    request: Request,
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> RuntimeAuthorizationResponse:
    service = RuntimeAuthorizationService(bundle.tokens, bundle.audit)
    correlation_id = request.headers.get("X-Correlation-ID")
    decision = service.authorize(
        AuthorizationRequest(
            token_id=payload.token_id,
            owner_sub=payload.owner_sub,
            requested_group=payload.group,
            requested_resource=payload.resource,
        ),
        correlation_id=correlation_id,
    )
    return RuntimeAuthorizationResponse(allowed=decision.allowed)