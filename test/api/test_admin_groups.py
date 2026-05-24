"""API tests for admin group-management routes."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.api.dependencies import require_admin_identity
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
def admin_client(app, admin_identity):
    app.dependency_overrides[require_admin_identity] = lambda: admin_identity
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


def test_create_group_as_admin(client, admin_client):
    response = client.post(
        "/v1/groups",
        json={
            "name": "plot.read",
            "description": "Read access to plot assets",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "plot.read"
    assert payload["description"] == "Read access to plot assets"
    assert payload["is_system"] is False
    assert payload["is_active"] is True


def test_create_group_rejects_duplicate_name(client, admin_client):
    first_response = client.post(
        "/v1/groups",
        json={"name": "plot.read", "description": "Read access to plot assets"},
    )
    second_response = client.post(
        "/v1/groups",
        json={"name": "plot.read", "description": "Duplicate create"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "Group already exists: plot.read"


def test_create_group_rejects_reserved_admin_name(client, admin_client):
    response = client.post(
        "/v1/groups",
        json={"name": "admin", "description": "Reserved group"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "The reserved admin group cannot be created via admin APIs"


def test_create_group_rejects_invalid_name(client, admin_client):
    response = client.post(
        "/v1/groups",
        json={"name": "not valid", "description": "Invalid group"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid group name: 'not valid'"