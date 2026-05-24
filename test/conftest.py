"""Shared pytest fixtures for gofr-sec tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMON_SRC = PROJECT_ROOT / "lib" / "gofr-common" / "src"

for path in (PROJECT_ROOT, COMMON_SRC):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@pytest.fixture(autouse=True)
def reset_test_settings(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Reset settings and provide isolated test directories for each test."""
    from app.settings import reset_settings

    data_dir = tmp_path / "gofr-sec-data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("GOFRSEC_ENV", "TEST")
    monkeypatch.setenv("GOFRSEC_HOST", "127.0.0.1")
    monkeypatch.setenv("GOFRSEC_MCP_PORT", "8060")
    monkeypatch.setenv("GOFRSEC_MCPO_PORT", "8061")
    monkeypatch.setenv("GOFRSEC_WEB_PORT", "8062")
    monkeypatch.setenv("GOFRSEC_DATA_DIR", str(data_dir))
    monkeypatch.setenv("GOFRSEC_LOG_LEVEL", "DEBUG")
    monkeypatch.delenv("GOFRSEC_BOOTSTRAP_ADMIN_SUBS", raising=False)
    monkeypatch.delenv("GOFRSEC_VAULT_URL", raising=False)
    monkeypatch.delenv("GOFRSEC_VAULT_TOKEN", raising=False)
    monkeypatch.delenv("GOFRSEC_VAULT_ROLE_ID", raising=False)
    monkeypatch.delenv("GOFRSEC_VAULT_SECRET_ID", raising=False)
    if request.node.get_closest_marker("vault_integration") is None:
        monkeypatch.delenv("GOFR_VAULT_URL", raising=False)
        monkeypatch.delenv("GOFR_VAULT_TOKEN", raising=False)
        monkeypatch.delenv("GOFR_VAULT_ROLE_ID", raising=False)
        monkeypatch.delenv("GOFR_VAULT_SECRET_ID", raising=False)

    reset_settings()
    yield data_dir
    reset_settings()


@pytest.fixture
def app():
    """Build the FastAPI app for API-level tests."""
    from app.web_server import GofrSecWebServer

    return GofrSecWebServer(version="test").app


@pytest.fixture
def client(app):
    """Return a FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def vault_client():
    """Build a Vault client for integration tests when Vault is available."""
    from gofr_common.auth.backends import VaultClient, VaultConfig

    vault_url = os.environ.get("GOFR_VAULT_URL")
    vault_token = os.environ.get("GOFR_VAULT_TOKEN")
    if not vault_url or not vault_token:
        pytest.skip("Vault integration environment is not configured")

    return VaultClient(VaultConfig(url=vault_url, token=vault_token, mount_point="secret"))