"""API tests for admin token minting."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib

import jwt
import pytest

from app.api.dependencies import require_admin_identity
from app.domain.models import GroupDefinition, UserProfile
from app.services.token_service import StaticTokenSigner
from gofr_common.auth import VerifiedIdentity
from gofr_common.testing.security_fixtures import generate_rsa_key_material


@pytest.fixture
def admin_identity() -> VerifiedIdentity:
    return VerifiedIdentity(
        subject="bootstrap-admin",
        issuer="https://keycloak.example/realms/gofr",
        audience=("gofr-sec",),
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def admin_token_app(app, admin_identity):
    key_material = generate_rsa_key_material("phase6-admin")
    app.dependency_overrides[require_admin_identity] = lambda: admin_identity
    app.state.token_signer = StaticTokenSigner(
        key_material.private_pem,
        algorithm="RS256",
        issuer="gofr-sec",
        key_id=key_material.kid,
    )
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        app.state.token_signer = None


def test_admin_can_mint_runtime_token(client, admin_token_app):
    repositories = admin_token_app.state.repositories
    repositories.user_profiles.upsert(UserProfile(keycloak_sub="kc-user-1"))
    repositories.groups.upsert(GroupDefinition(name="plot.read", description="Read access"))

    response = client.post(
        "/v1/users/kc-user-1/tokens",
        json={"groups": ["plot.read"], "expires_in_seconds": 600},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["owner_sub"] == "kc-user-1"
    assert payload["granted_groups"] == ["plot.read"]
    assert payload["status"] == "active"
    assert payload["issued_by_sub"] == "bootstrap-admin"
    assert len(payload["issued_token"].split(".")) == 3

    claims = jwt.decode(
        payload["issued_token"],
        admin_token_app.state.token_signer.public_key_pem(),
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
    assert claims["jti"] == payload["token_id"]
    assert claims["sub"] == "kc-user-1"
    assert claims["iss"] == "gofr-sec"
    assert "groups" not in claims

    record = repositories.tokens.get(payload["token_id"])
    assert record is not None
    assert record.owner_sub == "kc-user-1"
    assert record.granted_groups == ("plot.read",)
    assert record.jwt_hash == hashlib.sha256(payload["issued_token"].encode("ascii")).hexdigest()


def test_admin_can_inspect_token_metadata_without_raw_jwt(client, admin_token_app):
    repositories = admin_token_app.state.repositories
    repositories.user_profiles.upsert(UserProfile(keycloak_sub="kc-user-1"))
    repositories.groups.upsert(GroupDefinition(name="plot.read", description="Read access"))

    mint_response = client.post(
        "/v1/users/kc-user-1/tokens",
        json={"groups": ["plot.read"], "expires_in_seconds": 600},
    )
    token_id = mint_response.json()["token_id"]

    inspect_response = client.get(f"/v1/tokens/{token_id}")

    assert inspect_response.status_code == 200
    payload = inspect_response.json()
    assert payload["token_id"] == token_id
    assert payload["owner_sub"] == "kc-user-1"
    assert payload["granted_groups"] == ["plot.read"]
    assert "issued_token" not in payload


def test_admin_can_revoke_token(client, admin_token_app):
    repositories = admin_token_app.state.repositories
    repositories.user_profiles.upsert(UserProfile(keycloak_sub="kc-user-1"))
    repositories.groups.upsert(GroupDefinition(name="plot.read", description="Read access"))

    mint_response = client.post(
        "/v1/users/kc-user-1/tokens",
        json={"groups": ["plot.read"], "expires_in_seconds": 600},
    )
    token_id = mint_response.json()["token_id"]

    revoke_response = client.post(f"/v1/tokens/{token_id}/revoke")

    assert revoke_response.status_code == 200
    payload = revoke_response.json()
    assert payload["token_id"] == token_id
    assert payload["status"] == "revoked"
    assert payload["revoked_at"] is not None
    record = repositories.tokens.get(token_id)
    assert record is not None
    assert record.status == "revoked"
    assert record.revoked_at is not None