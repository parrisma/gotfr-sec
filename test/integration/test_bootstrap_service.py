"""Integration tests for first-boot bootstrap against Vault-backed repositories."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.services import BootstrapService

pytestmark = pytest.mark.vault_integration


def test_bootstrap_service_is_idempotent_with_vault_repositories(vault_client):
    from app.repositories import (
        VaultGroupMembershipRepository,
        VaultGroupRepository,
        VaultPathLayout,
    )

    paths = VaultPathLayout(path_prefix=f"gofr/sec-tests/{uuid4().hex[:8]}")
    groups = VaultGroupRepository(vault_client, paths)
    memberships = VaultGroupMembershipRepository(vault_client, paths)
    service = BootstrapService(groups, memberships)

    service.apply_plan(["bootstrap-admin"])
    service.apply_plan(["bootstrap-admin"])

    assert groups.get("admin") is not None
    assert memberships.count_members("admin") == 1
    assert memberships.has_membership("bootstrap-admin", "admin") is True


def test_app_startup_uses_vault_when_configured(monkeypatch):
    from app.settings import reset_settings
    from app.web_server import GofrSecWebServer

    vault_url = os.environ.get("GOFR_VAULT_URL")
    vault_token = os.environ.get("GOFR_VAULT_TOKEN")
    if not vault_url or not vault_token:
        pytest.skip("Vault integration environment is not configured")

    monkeypatch.setenv("GOFRSEC_VAULT_URL", vault_url)
    monkeypatch.setenv("GOFRSEC_VAULT_TOKEN", vault_token)
    monkeypatch.setenv("GOFRSEC_VAULT_PATH_PREFIX", f"gofr/sec-tests/{uuid4().hex[:8]}")
    monkeypatch.setenv("GOFRSEC_BOOTSTRAP_ADMIN_SUBS", "bootstrap-admin")
    reset_settings()

    app = GofrSecWebServer(version="test").app
    with TestClient(app) as test_client:
        repositories = test_client.app.state.repositories
        assert test_client.app.state.storage_backend == "vault"
        assert repositories.groups.get("admin") is not None
        assert repositories.memberships.has_membership("bootstrap-admin", "admin") is True