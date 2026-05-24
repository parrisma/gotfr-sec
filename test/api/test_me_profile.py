"""API tests for GET /v1/me."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.dependencies import get_verified_identity
from app.domain.models import UserGroupMembership, UserProfile
from gofr_common.auth import VerifiedIdentity


@pytest.fixture
def user_identity() -> VerifiedIdentity:
    return VerifiedIdentity(
        subject="kc-user-1",
        issuer="https://keycloak.example/realms/gofr",
        audience=("gofr-sec",),
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def user_app(app, user_identity):
    app.dependency_overrides[get_verified_identity] = lambda: user_identity
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


def test_get_me_returns_unregistered_view_without_side_effects(client, user_app):
    response = client.get("/v1/me")

    assert response.status_code == 200
    assert response.json() == {
        "keycloak_sub": "kc-user-1",
        "is_registered": False,
        "display_name": None,
        "email": None,
        "registered_at": None,
        "updated_at": None,
        "groups": [],
    }
    assert user_app.state.repositories.user_profiles.get("kc-user-1") is None


def test_get_me_returns_registered_profile_and_groups(client, user_app):
    repositories = user_app.state.repositories
    repositories.user_profiles.upsert(
        UserProfile(
            keycloak_sub="kc-user-1",
            display_name="Registered User",
            email="registered@example.com",
        )
    )
    repositories.memberships.add(
        UserGroupMembership(keycloak_sub="kc-user-1", group_name="plot.write")
    )
    repositories.memberships.add(
        UserGroupMembership(keycloak_sub="kc-user-1", group_name="plot.read")
    )

    response = client.get("/v1/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["keycloak_sub"] == "kc-user-1"
    assert payload["is_registered"] is True
    assert payload["display_name"] == "Registered User"
    assert payload["email"] == "registered@example.com"
    assert payload["groups"] == ["plot.read", "plot.write"]