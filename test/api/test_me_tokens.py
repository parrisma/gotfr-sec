"""API tests for GET /v1/me/tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.api.dependencies import get_verified_identity
from app.domain.models import IssuedTokenRecord
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
def user_tokens_app(app, user_identity):
    app.dependency_overrides[get_verified_identity] = lambda: user_identity
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


def test_get_me_tokens_returns_current_user_token_metadata_sorted(client, user_tokens_app):
    repositories = user_tokens_app.state.repositories
    now = datetime.now(timezone.utc)
    older_issued_at = now - timedelta(minutes=5)
    repositories.tokens.upsert(
        IssuedTokenRecord(
            token_id="older-token",
            owner_sub="kc-user-1",
            granted_groups=("plot.read",),
            issued_at=older_issued_at,
            issued_by_sub="bootstrap-admin",
        )
    )
    repositories.tokens.upsert(
        IssuedTokenRecord(
            token_id="newer-token",
            owner_sub="kc-user-1",
            granted_groups=("plot.write",),
            issued_at=now,
            issued_by_sub="bootstrap-admin",
        )
    )
    repositories.tokens.upsert(
        IssuedTokenRecord(
            token_id="other-user-token",
            owner_sub="kc-user-2",
            granted_groups=("plot.read",),
            issued_at=now + timedelta(minutes=1),
        )
    )

    response = client.get("/v1/me/tokens")

    assert response.status_code == 200
    expected_newer_issued_at = now.isoformat().replace("+00:00", "Z")
    expected_older_issued_at = older_issued_at.isoformat().replace("+00:00", "Z")
    assert response.json() == [
        {
            "token_id": "newer-token",
            "granted_groups": ["plot.write"],
            "status": "active",
            "issued_at": expected_newer_issued_at,
            "expires_at": None,
            "revoked_at": None,
            "issued_by_sub": "bootstrap-admin",
        },
        {
            "token_id": "older-token",
            "granted_groups": ["plot.read"],
            "status": "active",
            "issued_at": expected_older_issued_at,
            "expires_at": None,
            "revoked_at": None,
            "issued_by_sub": "bootstrap-admin",
        },
    ]


def test_get_me_tokens_returns_empty_list_without_side_effects(client, user_tokens_app):
    response = client.get("/v1/me/tokens")

    assert response.status_code == 200
    assert response.json() == []