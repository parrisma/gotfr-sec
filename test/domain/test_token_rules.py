"""Domain tests for Phase 6 token service behavior."""

from __future__ import annotations

from datetime import datetime, timezone

import jwt

from app.domain.models import GroupDefinition, UserProfile
from app.repositories.in_memory import (
    InMemoryAuditEventRepository,
    InMemoryGroupRepository,
    InMemoryTokenRepository,
    InMemoryUserProfileRepository,
)
from app.services.token_service import AdminTokenService, StaticTokenSigner
from gofr_common.testing.security_fixtures import generate_rsa_key_material


def test_admin_token_service_mints_minimal_runtime_claims():
    key_material = generate_rsa_key_material("phase6-domain")
    signer = StaticTokenSigner(key_material.private_pem, issuer="gofr-sec", key_id=key_material.kid)
    groups = InMemoryGroupRepository()
    users = InMemoryUserProfileRepository()
    tokens = InMemoryTokenRepository()
    audit = InMemoryAuditEventRepository()
    groups.upsert(GroupDefinition(name="plot.read", description="Read access"))
    users.upsert(UserProfile(keycloak_sub="kc-user-1"))

    service = AdminTokenService(groups, users, tokens, audit, signer, default_lifetime_seconds=600)

    minted = service.mint_token(
        owner_sub="kc-user-1",
        groups=["plot.read"],
        actor_sub="bootstrap-admin",
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    claims = jwt.decode(
        minted.raw_token,
        signer.public_key_pem(),
        algorithms=["RS256"],
        options={"verify_aud": False, "verify_exp": False},
    )
    assert claims["jti"] == minted.record.token_id
    assert claims["sub"] == "kc-user-1"
    assert claims["iss"] == "gofr-sec"
    assert claims["iat"] == claims["nbf"]
    assert claims["exp"] > claims["iat"]
    assert "groups" not in claims


def test_admin_token_service_revokes_existing_record():
    key_material = generate_rsa_key_material("phase6-domain-revoke")
    signer = StaticTokenSigner(key_material.private_pem, issuer="gofr-sec", key_id=key_material.kid)
    groups = InMemoryGroupRepository()
    users = InMemoryUserProfileRepository()
    tokens = InMemoryTokenRepository()
    audit = InMemoryAuditEventRepository()
    groups.upsert(GroupDefinition(name="plot.read", description="Read access"))
    users.upsert(UserProfile(keycloak_sub="kc-user-1"))

    service = AdminTokenService(groups, users, tokens, audit, signer, default_lifetime_seconds=600)
    minted = service.mint_token(
        owner_sub="kc-user-1",
        groups=["plot.read"],
        actor_sub="bootstrap-admin",
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    revoked = service.revoke_token(
        token_id=minted.record.token_id,
        actor_sub="bootstrap-admin",
        now=datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc),
    )

    assert revoked.status == "revoked"
    assert revoked.revoked_at == datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)