"""Integration tests for admin audit events with Vault-backed repositories."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import require_admin_identity
from app.domain.models import UserProfile
from app.settings import reset_settings
from app.web_server import GofrSecWebServer
from gofr_common.auth import VerifiedIdentity

pytestmark = pytest.mark.vault_integration


def test_admin_group_and_membership_actions_are_audited(monkeypatch):
    vault_url = os.environ.get("GOFR_VAULT_URL")
    vault_token = os.environ.get("GOFR_VAULT_TOKEN")
    if not vault_url or not vault_token:
        pytest.skip("Vault integration environment is not configured")

    monkeypatch.setenv("GOFRSEC_VAULT_URL", vault_url)
    monkeypatch.setenv("GOFRSEC_VAULT_TOKEN", vault_token)
    monkeypatch.setenv("GOFRSEC_VAULT_PATH_PREFIX", f"gofr/sec-tests/{uuid4().hex[:8]}")
    reset_settings()

    admin_identity = VerifiedIdentity(
        subject="bootstrap-admin",
        issuer="https://keycloak.example/realms/gofr",
        audience=("gofr-sec",),
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )

    app = GofrSecWebServer(version="test").app
    app.dependency_overrides[require_admin_identity] = lambda: admin_identity

    try:
        with TestClient(app) as client:
            repositories = client.app.state.repositories
            repositories.user_profiles.upsert(UserProfile(keycloak_sub="kc-user-1"))

            create_group_response = client.post(
                "/v1/groups",
                json={"name": "plot.read", "description": "Read access"},
                headers={"X-Correlation-ID": "corr-group-create"},
            )
            duplicate_group_response = client.post(
                "/v1/groups",
                json={"name": "plot.read", "description": "Duplicate"},
                headers={"X-Correlation-ID": "corr-group-duplicate"},
            )
            add_membership_response = client.post(
                "/v1/users/kc-user-1/groups/plot.read",
                headers={"X-Correlation-ID": "corr-membership-add"},
            )
            remove_missing_admin_response = client.delete(
                "/v1/users/bootstrap-admin/groups/admin",
                headers={"X-Correlation-ID": "corr-admin-remove"},
            )

            audit_events = repositories.audit.list_all()

        assert create_group_response.status_code == 201
        assert duplicate_group_response.status_code == 409
        assert add_membership_response.status_code == 200
        assert remove_missing_admin_response.status_code == 404
        assert [(event.event_type, event.result) for event in audit_events] == [
            ("admin.group.create", "success"),
            ("admin.group.create", "failure"),
            ("admin.group_membership.add", "success"),
            ("admin.group_membership.remove", "failure"),
        ]
        assert [event.correlation_id for event in audit_events] == [
            "corr-group-create",
            "corr-group-duplicate",
            "corr-membership-add",
            "corr-admin-remove",
        ]
    finally:
        app.dependency_overrides.clear()