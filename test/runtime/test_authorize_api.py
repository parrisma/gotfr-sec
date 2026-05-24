"""Runtime API tests for authorization decisions and contract flow."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from app.domain.models import GroupDefinition, UserProfile
from app.services.token_service import AdminTokenService, StaticTokenSigner
from gofr_common.auth import GofrSecClientSettings, RuntimeAuthorizer
from gofr_common.testing.security_fixtures import generate_rsa_key_material


@pytest.fixture
def runtime_app(app):
    key_material = generate_rsa_key_material("runtime-authorize")
    app.state.token_signer = StaticTokenSigner(
        key_material.private_pem,
        issuer="gofr-sec",
        key_id=key_material.kid,
    )
    app.state.runtime_test_key_material = key_material
    try:
        yield app
    finally:
        app.state.token_signer = None
        app.state.runtime_test_key_material = None


def mint_runtime_token(runtime_app, *, group_name: str = "plot.read"):
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
    return service.mint_token(
        owner_sub="kc-user-1",
        groups=[group_name],
        actor_sub="bootstrap-admin",
        now=datetime.now(timezone.utc),
    )


def test_runtime_authorize_allows_matching_group(client, runtime_app):
    minted = mint_runtime_token(runtime_app)

    response = client.post(
        "/v1/runtime/authorize",
        json={
            "token_id": minted.record.token_id,
            "owner_sub": "kc-user-1",
            "group": "plot.read",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"allowed": True}


def test_runtime_authorization_flow_verifies_locally_and_authorizes_against_app(runtime_app):
    with TestClient(runtime_app) as test_client:
        runtime_app.state.token_signer = StaticTokenSigner(
            runtime_app.state.runtime_test_key_material.private_pem,
            issuer="gofr-sec",
            key_id=runtime_app.state.runtime_test_key_material.kid,
        )
        minted = mint_runtime_token(runtime_app)
        authorizer = RuntimeAuthorizer.from_settings(
            GofrSecClientSettings(base_url="http://testserver", token_issuer="gofr-sec"),
            client=test_client,
        )
        try:
            result = authorizer.authorize(minted.raw_token, group="plot.read", correlation_id="corr-7")
        finally:
            authorizer.close()

    assert result.decision.allowed is True
    assert result.from_cache is False
    assert result.verified_token.token_id == minted.record.token_id
    assert result.verified_token.owner_sub == "kc-user-1"