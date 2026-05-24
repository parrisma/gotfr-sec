"""API tests for admin membership-management routes."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.dependencies import require_admin_identity
from app.domain.models import GroupDefinition, UserGroupMembership, UserProfile
from gofr_common.auth import VerifiedIdentity


@pytest.fixture
def admin_identity() -> VerifiedIdentity:
    return VerifiedIdentity(
        subject="bootstrap-admin",
        issuer="https://keycloak.example/realms/gofr",
        audience=("gofr-sec",),
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def admin_app(app, admin_identity):
    app.dependency_overrides[require_admin_identity] = lambda: admin_identity
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


def test_add_group_membership_as_admin(client, admin_app):
    repositories = admin_app.state.repositories
    repositories.groups.upsert(GroupDefinition(name="plot.read"))
    repositories.user_profiles.upsert(UserProfile(keycloak_sub="kc-user-1"))

    response = client.post("/v1/users/kc-user-1/groups/plot.read")

    assert response.status_code == 200
    payload = response.json()
    assert payload["keycloak_sub"] == "kc-user-1"
    assert payload["group_name"] == "plot.read"
    assert payload["granted_by_sub"] == "bootstrap-admin"
    assert repositories.memberships.has_membership("kc-user-1", "plot.read") is True


def test_add_group_membership_rejects_unknown_target_user(client, admin_app):
    repositories = admin_app.state.repositories
    repositories.groups.upsert(GroupDefinition(name="plot.read"))

    response = client.post("/v1/users/kc-user-404/groups/plot.read")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown target user: kc-user-404"


def test_remove_group_membership_as_admin(client, admin_app):
    repositories = admin_app.state.repositories
    repositories.groups.upsert(GroupDefinition(name="plot.read"))
    repositories.user_profiles.upsert(UserProfile(keycloak_sub="kc-user-1"))
    repositories.memberships.add(
        UserGroupMembership(keycloak_sub="kc-user-1", group_name="plot.read")
    )

    response = client.delete("/v1/users/kc-user-1/groups/plot.read")

    assert response.status_code == 204
    assert repositories.memberships.has_membership("kc-user-1", "plot.read") is False


def test_remove_last_admin_membership_is_rejected(client, admin_app):
    repositories = admin_app.state.repositories
    repositories.memberships.add(
        UserGroupMembership(keycloak_sub="bootstrap-admin", group_name="admin")
    )

    response = client.delete("/v1/users/bootstrap-admin/groups/admin")

    assert response.status_code == 409
    assert response.json()["detail"] == "At least one admin membership must remain"