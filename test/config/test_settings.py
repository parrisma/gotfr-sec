"""Settings tests for the gofr-sec bootstrap configuration."""

from app.settings import (
    DEFAULT_MCPO_PORT,
    DEFAULT_MCP_PORT,
    DEFAULT_WEB_PORT,
    get_settings,
    reset_settings,
)


def test_settings_use_project_defaults():
    settings = get_settings(reload=True, require_auth=False)

    assert settings.server.mcp_port == DEFAULT_MCP_PORT
    assert settings.server.mcpo_port == DEFAULT_MCPO_PORT
    assert settings.server.web_port == DEFAULT_WEB_PORT
    assert settings.log.level == "DEBUG"


def test_settings_read_gofrsec_environment(monkeypatch):
    monkeypatch.setenv("GOFRSEC_HOST", "0.0.0.0")
    monkeypatch.setenv("GOFRSEC_WEB_PORT", "9062")
    monkeypatch.setenv("GOFRSEC_MCP_PORT", "9060")
    monkeypatch.setenv("GOFRSEC_MCPO_PORT", "9061")
    reset_settings()

    settings = get_settings(reload=True, require_auth=False)

    assert settings.server.host == "0.0.0.0"
    assert settings.server.web_port == 9062
    assert settings.server.mcp_port == 9060
    assert settings.server.mcpo_port == 9061


def test_settings_auth_can_be_disabled_for_bootstrap():
    settings = get_settings(reload=True, require_auth=False)

    assert settings.auth.require_auth is False
    assert settings.auth.jwt_secret is None