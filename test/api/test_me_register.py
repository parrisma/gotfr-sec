"""API tests for POST /v1/me/register."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.dependencies import get_verified_identity
from gofr_common.auth import VerifiedIdentity


@pytest.fixture
def user_identity() -> VerifiedIdentity:
    return VerifiedIdentity(
        subject="kc-user-1",
        issuer="https://keycloak.example/realms/gofr",
        audience=("gofr-sec",),
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        claims={
            "name": "Test User",
            "email": "user@example.com",
        },
    )


@pytest.fixture
def user_app(app, user_identity):
    app.dependency_overrides[get_verified_identity] = lambda: user_identity
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


def test_register_me_creates_local_profile(client, user_app):
    response = client.post("/v1/me/register")

    assert response.status_code == 200
    payload = response.json()
    assert payload["keycloak_sub"] == "kc-user-1"
    assert payload["display_name"] == "Test User"
    assert payload["email"] == "user@example.com"
    assert payload["registration_status"] == "created"
    assert user_app.state.repositories.memberships.list_for_user("kc-user-1") == []


def test_register_me_is_idempotent(client, user_app):
    first_response = client.post("/v1/me/register")
    second_response = client.post("/v1/me/register")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["registration_status"] == "created"
    assert second_response.json()["registration_status"] == "refreshed"
    assert second_response.json()["registered_at"] == first_response.json()["registered_at"]

    audit_events = user_app.state.repositories.audit.list_all()
    assert [event.result for event in audit_events] == ["created", "refreshed"]