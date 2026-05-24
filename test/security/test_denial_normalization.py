"""Security tests for normalized runtime denial behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.models import GroupDefinition, IssuedTokenRecord, UserProfile
from app.services.token_service import AdminTokenService, StaticTokenSigner
from gofr_common.testing.security_fixtures import generate_rsa_key_material


@pytest.fixture
def runtime_app(app):
    key_material = generate_rsa_key_material("runtime-deny")
    app.state.token_signer = StaticTokenSigner(
        key_material.private_pem,
        issuer="gofr-sec",
        key_id=key_material.kid,
    )
    try:
        yield app
    finally:
        app.state.token_signer = None


def mint_token(runtime_app, *, issued_at: datetime, expires_at: datetime | None, group_name: str = "plot.read"):
    repositories = runtime_app.state.repositories
    repositories.user_profiles.upsert(UserProfile(keycloak_sub="kc-user-1"))
    repositories.groups.upsert(GroupDefinition(name=group_name, description="Runtime access"))
    service = AdminTokenService(
        repositories.groups,
        repositories.user_profiles,
        repositories.tokens,
        repositories.audit,
        runtime_app.state.token_signer,
    )
    lifetime_seconds = int((expires_at - issued_at).total_seconds()) if expires_at is not None else 3600
    return service.mint_token(
        owner_sub="kc-user-1",
        groups=[group_name],
        actor_sub="bootstrap-admin",
        now=issued_at,
        expires_in_seconds=lifetime_seconds,
    )


def test_runtime_authorize_denials_share_the_same_outward_shape(client, runtime_app):
    now = datetime.now(timezone.utc)
    active_token = mint_token(
        runtime_app,
        issued_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    revoked_token = mint_token(
        runtime_app,
        issued_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    repositories = runtime_app.state.repositories
    repositories.tokens.upsert(
        IssuedTokenRecord(
            token_id=revoked_token.record.token_id,
            owner_sub=revoked_token.record.owner_sub,
            granted_groups=revoked_token.record.granted_groups,
            status="revoked",
            issued_at=revoked_token.record.issued_at,
            expires_at=revoked_token.record.expires_at,
            issued_by_sub=revoked_token.record.issued_by_sub,
            jwt_hash=revoked_token.record.jwt_hash,
            revoked_at=now,
        )
    )
    expired_token = mint_token(
        runtime_app,
        issued_at=now - timedelta(minutes=20),
        expires_at=now - timedelta(minutes=10),
    )

    responses = [
        client.post(
            "/v1/runtime/authorize",
            json={"token_id": "unknown-token", "owner_sub": "kc-user-1", "group": "plot.read"},
        ),
        client.post(
            "/v1/runtime/authorize",
            json={"token_id": revoked_token.record.token_id, "owner_sub": "kc-user-1", "group": "plot.read"},
        ),
        client.post(
            "/v1/runtime/authorize",
            json={"token_id": expired_token.record.token_id, "owner_sub": "kc-user-1", "group": "plot.read"},
        ),
        client.post(
            "/v1/runtime/authorize",
            json={"token_id": active_token.record.token_id, "owner_sub": "kc-user-1", "group": "plot.write"},
        ),
        client.post(
            "/v1/runtime/authorize",
            json={"token_id": active_token.record.token_id, "owner_sub": "wrong-owner", "group": "plot.read"},
        ),
        client.post(
            "/v1/runtime/authorize",
            json={"token_id": active_token.record.token_id, "owner_sub": "kc-user-1", "resource": "missing.resource"},
        ),
    ]

    assert all(response.status_code == 200 for response in responses)
    assert all(response.json() == {"allowed": False} for response in responses)