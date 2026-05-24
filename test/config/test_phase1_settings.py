"""Tests for gofr-sec-specific settings sections added in Phase 1."""

from app.settings import get_service_settings, reset_settings


def test_service_settings_parse_phase1_sections(monkeypatch):
    monkeypatch.setenv("GOFRSEC_KEYCLOAK_ISSUER_URL", "https://keycloak.local/realms/gofr")
    monkeypatch.setenv("GOFRSEC_KEYCLOAK_AUDIENCE", "gofr-sec")
    monkeypatch.setenv("GOFRSEC_BOOTSTRAP_ADMIN_SUBS", "sub-a, sub-b, sub-a")
    monkeypatch.setenv("GOFRSEC_SIGNING_VAULT_PATH", "gofr/sec/test/signing/runtime")
    monkeypatch.setenv("GOFRSEC_SIGNING_ALGORITHM", "RS256")
    monkeypatch.setenv("GOFRSEC_TOKEN_ISSUER", "https://gofr-sec.local")
    monkeypatch.setenv("GOFRSEC_TOKEN_DEFAULT_LIFETIME_S", "900")
    monkeypatch.setenv("GOFRSEC_AUTHZ_CACHE_TTL_S", "45")
    monkeypatch.setenv("GOFRSEC_PUBLIC_KEY_CACHE_TTL_S", "600")
    monkeypatch.setenv("GOFRSEC_VAULT_URL", "http://localhost:8306")
    monkeypatch.setenv("GOFRSEC_VAULT_TOKEN", "test-token")
    monkeypatch.setenv("GOFRSEC_VAULT_PATH_PREFIX", "gofr/sec/test")
    reset_settings()

    settings = get_service_settings(reload=True, require_auth=False)

    assert settings.keycloak.issuer_url == "https://keycloak.local/realms/gofr"
    assert settings.keycloak.audience == "gofr-sec"
    assert settings.bootstrap.trusted_subs == ("sub-a", "sub-b")
    assert settings.signing.vault_path == "gofr/sec/test/signing/runtime"
    assert settings.signing.algorithm == "RS256"
    assert settings.signing.issuer == "https://gofr-sec.local"
    assert settings.signing.default_lifetime_seconds == 900
    assert settings.cache.authz_ttl_seconds == 45
    assert settings.cache.public_key_ttl_seconds == 600
    assert settings.vault.url == "http://localhost:8306"
    assert settings.vault.token == "test-token"
    assert settings.vault.path_prefix == "gofr/sec/test"
    assert settings.vault.is_configured() is True


def test_service_settings_reuse_core_settings_defaults(monkeypatch):
    monkeypatch.delenv("GOFR_VAULT_URL", raising=False)
    monkeypatch.delenv("GOFR_VAULT_TOKEN", raising=False)
    monkeypatch.delenv("GOFR_VAULT_ROLE_ID", raising=False)
    monkeypatch.delenv("GOFR_VAULT_SECRET_ID", raising=False)
    reset_settings()

    settings = get_service_settings(reload=True, require_auth=False)

    assert settings.core.server.web_port == 8062
    assert settings.bootstrap.trusted_subs == ()
    assert settings.signing.algorithm == "RS256"
    assert settings.signing.issuer == "gofr-sec"
    assert settings.signing.default_lifetime_seconds == 3600
    assert settings.cache.authz_ttl_seconds == 30
    assert settings.vault.path_prefix == "gofr/sec"
    assert settings.vault.is_configured() is False


def test_service_settings_allow_global_vault_fallback(monkeypatch):
    monkeypatch.setenv("GOFR_VAULT_URL", "http://localhost:9300")
    monkeypatch.setenv("GOFR_VAULT_TOKEN", "global-token")
    reset_settings()

    settings = get_service_settings(reload=True, require_auth=False)

    assert settings.vault.url == "http://localhost:9300"
    assert settings.vault.token == "global-token"
    assert settings.vault.is_configured() is True