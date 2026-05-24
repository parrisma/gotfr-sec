"""FastAPI dependencies for accessing application state."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from gofr_common.auth import AccessTokenVerificationError, AccessTokenVerifier, VerifiedIdentity

from app.bootstrap import RepositoryBundle
from app.domain.rules import RESERVED_ADMIN_GROUP
from app.settings import GofrSecServiceSettings

_bearer_scheme = HTTPBearer(auto_error=False)


def get_repository_bundle(request: Request) -> RepositoryBundle:
    return request.app.state.repositories


def get_service_settings_dependency(request: Request) -> GofrSecServiceSettings:
    return request.app.state.service_settings


def get_access_token_verifier(request: Request) -> AccessTokenVerifier:
    return request.app.state.access_token_verifier


def get_verified_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    verifier: AccessTokenVerifier = Depends(get_access_token_verifier),
) -> VerifiedIdentity:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return verifier.verify(credentials.credentials)
    except AccessTokenVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_admin_identity(
    identity: VerifiedIdentity = Depends(get_verified_identity),
    bundle: RepositoryBundle = Depends(get_repository_bundle),
) -> VerifiedIdentity:
    if not bundle.memberships.has_membership(identity.subject, RESERVED_ADMIN_GROUP):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return identity