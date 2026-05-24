"""Security tests for Phase 6 signing key behavior."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.dependencies import require_admin_identity
from app.domain.models import GroupDefinition, UserProfile
from gofr_common.auth import VerifiedIdentity


@pytest.fixture
def admin_identity() -> VerifiedIdentity:
    return VerifiedIdentity(
        subject="bootstrap-admin",
        issuer="https://keycloak.example/realms/gofr",
        audience=("gofr-sec",),
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )


def test_admin_token_route_fails_closed_when_signing_is_unavailable(client, app, admin_identity):
    app.dependency_overrides[require_admin_identity] = lambda: admin_identity
    try:
        repositories = app.state.repositories
        repositories.user_profiles.upsert(UserProfile(keycloak_sub="kc-user-1"))
        repositories.groups.upsert(GroupDefinition(name="plot.read", description="Read access"))

        response = client.post(
            "/v1/users/kc-user-1/tokens",
            json={"groups": ["plot.read"], "expires_in_seconds": 600},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Token signing is unavailable"