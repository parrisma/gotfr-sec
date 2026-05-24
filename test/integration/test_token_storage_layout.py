"""Integration tests for Phase 6 Vault-backed token signing and storage."""

from __future__ import annotations

from uuid import uuid4

import jwt
import pytest

from app.domain.models import GroupDefinition, UserProfile
from app.repositories import VaultGroupRepository, VaultPathLayout, VaultTokenRepository, VaultUserRepository
from app.repositories.audit import LoggingAuditEventRepository
from app.services.token_service import AdminTokenService, VaultTokenSigner
from gofr_common.testing.security_fixtures import generate_rsa_key_material

pytestmark = pytest.mark.vault_integration


@pytest.fixture
def vault_paths() -> VaultPathLayout:
    return VaultPathLayout(path_prefix=f"gofr/sec-tests/{uuid4().hex[:8]}")


def test_vault_signing_and_token_storage_round_trip(vault_client, vault_paths):
    key_material = generate_rsa_key_material("vault-phase6")
    vault_client.write_secret(
        vault_paths.signing_key_path(),
        {
            "private_key_pem": key_material.private_pem.decode("ascii"),
            "kid": key_material.kid,
        },
    )

    groups = VaultGroupRepository(vault_client, vault_paths)
    users = VaultUserRepository(vault_client, vault_paths)
    tokens = VaultTokenRepository(vault_client, vault_paths)
    audit = LoggingAuditEventRepository()
    groups.upsert(GroupDefinition(name="plot.read", description="Read access"))
    users.upsert(UserProfile(keycloak_sub="kc-user-1"))

    signer = VaultTokenSigner(
        vault_client,
        vault_paths.signing_key_path(),
        algorithm="RS256",
        issuer="gofr-sec",
    )
    service = AdminTokenService(groups, users, tokens, audit, signer, default_lifetime_seconds=600)

    minted = service.mint_token(
        owner_sub="kc-user-1",
        groups=["plot.read"],
        actor_sub="bootstrap-admin",
    )

    claims = jwt.decode(
        minted.raw_token,
        signer.public_key_pem(),
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
    assert claims["jti"] == minted.record.token_id
    assert claims["sub"] == "kc-user-1"
    assert vault_client.secret_exists(vault_paths.signing_key_path()) is True
    assert vault_client.secret_exists(vault_paths.token_path(minted.record.token_id)) is True
    assert vault_client.secret_exists(
        vault_paths.user_token_path("kc-user-1", minted.record.token_id)
    ) is True
    assert vault_client.secret_exists(
        vault_paths.group_token_path("plot.read", minted.record.token_id)
    ) is True

    revoked = service.revoke_token(
        token_id=minted.record.token_id,
        actor_sub="bootstrap-admin",
    )

    assert revoked.status == "revoked"
    stored = tokens.get(minted.record.token_id)
    assert stored is not None
    assert stored.status == "revoked"
    assert stored.revoked_at is not None