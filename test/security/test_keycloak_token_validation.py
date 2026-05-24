"""Security tests for Keycloak token validation on self-service routes."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.settings import reset_settings
from app.web_server import GofrSecWebServer
from gofr_common.auth import AccessTokenVerifier, KeycloakVerifierSettings
from gofr_common.testing.security_fixtures import (
    build_issuer_metadata_document,
    build_jwks_document,
    build_oidc_mock_handler,
    generate_rsa_key_material,
    sign_access_token,
)

ISSUER_URL = "https://keycloak.example/realms/gofr"
AUDIENCE = "gofr-sec"


def build_security_client(monkeypatch):
    monkeypatch.setenv("GOFRSEC_KEYCLOAK_ISSUER_URL", ISSUER_URL)
    monkeypatch.setenv("GOFRSEC_KEYCLOAK_AUDIENCE", AUDIENCE)
    reset_settings()

    key_material = generate_rsa_key_material("kc-user-key")
    issuer_metadata = build_issuer_metadata_document(ISSUER_URL)
    jwks_document = build_jwks_document(key_material)
    mock_handler = build_oidc_mock_handler(issuer_metadata, jwks_document)
    verifier_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    verifier = AccessTokenVerifier.from_settings(
        KeycloakVerifierSettings(issuer_url=ISSUER_URL, audience=AUDIENCE),
        client=verifier_client,
    )

    app = GofrSecWebServer(version="test").app
    return app, verifier, key_material


def test_me_register_rejects_invalid_access_token(monkeypatch):
    app, verifier, key_material = build_security_client(monkeypatch)

    with TestClient(app) as client:
        client.app.state.access_token_verifier.close()
        client.app.state.access_token_verifier = verifier
        invalid_token = sign_access_token(
            key_material,
            issuer_url=ISSUER_URL,
            audience="wrong-audience",
            subject="kc-user-1",
        )

        response = client.post(
            "/v1/me/register",
            headers={"Authorization": f"Bearer {invalid_token}"},
        )

    assert response.status_code == 401
    assert response.json()["detail"].startswith("Invalid access token:")


def test_me_profile_requires_bearer_token(monkeypatch):
    app, verifier, _key_material = build_security_client(monkeypatch)

    with TestClient(app) as client:
        client.app.state.access_token_verifier.close()
        client.app.state.access_token_verifier = verifier
        response = client.get("/v1/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


def test_me_route_allows_verified_non_admin_user(monkeypatch):
    app, verifier, key_material = build_security_client(monkeypatch)

    with TestClient(app) as client:
        client.app.state.access_token_verifier.close()
        client.app.state.access_token_verifier = verifier
        token = sign_access_token(
            key_material,
            issuer_url=ISSUER_URL,
            audience=AUDIENCE,
            subject="kc-user-1",
        )

        response = client.get(
            "/v1/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["keycloak_sub"] == "kc-user-1"
    assert response.json()["is_registered"] is False