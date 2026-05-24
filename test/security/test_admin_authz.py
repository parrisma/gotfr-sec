"""Security tests for admin authentication and authorization dependencies."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.domain.models import UserGroupMembership
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

    key_material = generate_rsa_key_material("kc-admin-key")
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


def test_admin_group_route_rejects_invalid_access_token(monkeypatch):
    app, verifier, key_material = build_security_client(monkeypatch)

    with TestClient(app) as client:
        client.app.state.access_token_verifier.close()
        client.app.state.access_token_verifier = verifier
        invalid_token = sign_access_token(
            key_material,
            issuer_url=ISSUER_URL,
            audience="wrong-audience",
            subject="kc-admin",
        )

        response = client.post(
            "/v1/groups",
            json={"name": "plot.read", "description": "Read access"},
            headers={"Authorization": f"Bearer {invalid_token}"},
        )

    assert response.status_code == 401
    assert response.json()["detail"].startswith("Invalid access token:")


def test_admin_group_route_rejects_non_admin_caller(monkeypatch):
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

        response = client.post(
            "/v1/groups",
            json={"name": "plot.read", "description": "Read access"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_group_route_allows_verified_admin(monkeypatch):
    app, verifier, key_material = build_security_client(monkeypatch)

    with TestClient(app) as client:
        client.app.state.access_token_verifier.close()
        client.app.state.access_token_verifier = verifier
        client.app.state.repositories.memberships.add(
            UserGroupMembership(keycloak_sub="kc-admin", group_name="admin")
        )
        token = sign_access_token(
            key_material,
            issuer_url=ISSUER_URL,
            audience=AUDIENCE,
            subject="kc-admin",
        )

        response = client.post(
            "/v1/groups",
            json={"name": "plot.write", "description": "Write access"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    assert response.json()["name"] == "plot.write"