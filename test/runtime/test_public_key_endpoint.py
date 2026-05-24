"""Runtime API tests for the public verification-key endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.services.token_service import StaticTokenSigner
from gofr_common.testing.security_fixtures import generate_rsa_key_material


@pytest.fixture
def runtime_app(app):
    key_material = generate_rsa_key_material("runtime-public")
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


def test_public_key_endpoint_returns_jwks_document(client, runtime_app):
    now = datetime.now(timezone.utc)
    token = runtime_app.state.token_signer.sign_token(
        token_id="token-1",
        owner_sub="user-1",
        issued_at=now,
        expires_at=now + timedelta(minutes=10),
    )

    response = client.get("/v1/runtime/keys/public")

    assert response.status_code == 200
    payload = response.json()
    assert payload["keys"][0]["kid"] == runtime_app.state.runtime_test_key_material.kid
    verified_claims = jwt.decode(
        token,
        jwt.PyJWK.from_dict(payload["keys"][0]).key,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )
    assert verified_claims["jti"] == "token-1"