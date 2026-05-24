"""Application bootstrap wiring for repositories and startup state."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from gofr_common.auth import AccessTokenVerifier, KeycloakVerifierSettings
from gofr_common.auth.backends import VaultClient

from app.repositories import (
    InMemoryGroupMembershipRepository,
    InMemoryGroupRepository,
    InMemoryTokenRepository,
    InMemoryUserProfileRepository,
)
from app.repositories.audit import LoggingAuditEventRepository
from app.repositories.interfaces import (
    AuditEventRepository,
    GroupMembershipRepository,
    GroupRepository,
    TokenRepository,
    UserProfileRepository,
)
from app.repositories.vault_groups import VaultGroupMembershipRepository, VaultGroupRepository
from app.repositories.vault_paths import VaultPathLayout
from app.repositories.vault_tokens import VaultTokenRepository
from app.repositories.vault_users import VaultUserRepository
from app.services import BootstrapPlan, BootstrapService
from app.services.token_service import build_token_signer
from app.settings import GofrSecServiceSettings, get_service_settings


@dataclass(frozen=True)
class RepositoryBundle:
    """Runtime repository bundle attached to the FastAPI app state."""

    user_profiles: UserProfileRepository
    groups: GroupRepository
    memberships: GroupMembershipRepository
    tokens: TokenRepository
    audit: AuditEventRepository
    storage_backend: str
    vault_client: VaultClient | None = None


def build_repository_bundle(settings: GofrSecServiceSettings) -> RepositoryBundle:
    """Create the repository bundle for the current service settings."""
    audit_repository = LoggingAuditEventRepository()

    if settings.vault.is_configured():
        vault_client = VaultClient(settings.vault.to_vault_config())
        paths = VaultPathLayout(path_prefix=settings.vault.path_prefix)
        return RepositoryBundle(
            user_profiles=VaultUserRepository(vault_client, paths),
            groups=VaultGroupRepository(vault_client, paths),
            memberships=VaultGroupMembershipRepository(vault_client, paths),
            tokens=VaultTokenRepository(vault_client, paths),
            audit=audit_repository,
            storage_backend="vault",
            vault_client=vault_client,
        )

    return RepositoryBundle(
        user_profiles=InMemoryUserProfileRepository(),
        groups=InMemoryGroupRepository(),
        memberships=InMemoryGroupMembershipRepository(),
        tokens=InMemoryTokenRepository(),
        audit=audit_repository,
        storage_backend="memory",
        vault_client=None,
    )


def initialize_application_state(app: FastAPI) -> BootstrapPlan:
    """Initialize repositories and apply first-boot bootstrap state."""
    settings = get_service_settings(reload=False, require_auth=False)
    bundle = build_repository_bundle(settings)
    paths = VaultPathLayout(path_prefix=settings.vault.path_prefix)
    bootstrap_service = BootstrapService(bundle.groups, bundle.memberships)
    access_token_verifier = AccessTokenVerifier.from_settings(
        KeycloakVerifierSettings(
            issuer_url=settings.keycloak.issuer_url,
            audience=settings.keycloak.audience,
            jwks_cache_ttl_seconds=settings.cache.public_key_ttl_seconds,
        )
    )
    token_signer = build_token_signer(
        vault_client=bundle.vault_client,
        paths=paths,
        settings=settings.signing,
    )
    plan = bootstrap_service.apply_plan(settings.bootstrap.trusted_subs)

    app.state.service_settings = settings
    app.state.repositories = bundle
    app.state.access_token_verifier = access_token_verifier
    app.state.token_signer = token_signer
    app.state.bootstrap_plan = plan
    app.state.storage_backend = bundle.storage_backend

    return plan