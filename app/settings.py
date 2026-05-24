"""Project settings wrapper for gofr-sec."""

from dataclasses import dataclass
import os
from pathlib import Path

from gofr_common.auth.backends import VaultConfig
from gofr_common.config import (
    AuthSettings,
    Config,
    LogSettings,
    ServerSettings,
    Settings,
    StorageSettings,
    get_default_storage_dir,
    get_default_token_store_path,
)

_ENV_PREFIX = "GOFRSEC"
_PROJECT_ROOT = Path(__file__).parent.parent

DEFAULT_MCP_PORT = 8060
DEFAULT_MCPO_PORT = 8061
DEFAULT_WEB_PORT = 8062

_settings: Settings | None = None
_service_settings: "GofrSecServiceSettings | None" = None


def _split_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()

    items: list[str] = []
    seen: set[str] = set()
    for item in value.split(","):
        normalized = item.strip()
        if normalized and normalized not in seen:
            items.append(normalized)
            seen.add(normalized)
    return tuple(items)


@dataclass(frozen=True)
class KeycloakSettings:
    """Keycloak settings used by gofr-sec."""

    issuer_url: str | None = None
    audience: str | None = None

    @classmethod
    def from_env(cls, prefix: str = _ENV_PREFIX) -> "KeycloakSettings":
        return cls(
            issuer_url=os.getenv(f"{prefix}_KEYCLOAK_ISSUER_URL"),
            audience=os.getenv(f"{prefix}_KEYCLOAK_AUDIENCE"),
        )


@dataclass(frozen=True)
class BootstrapAdminSettings:
    """Bootstrap admin subject configuration."""

    trusted_subs: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, prefix: str = _ENV_PREFIX) -> "BootstrapAdminSettings":
        return cls(trusted_subs=_split_csv(os.getenv(f"{prefix}_BOOTSTRAP_ADMIN_SUBS")))


@dataclass(frozen=True)
class SigningSettings:
    """Signing-key configuration for gofr-sec-issued JWTs."""

    vault_path: str | None = None
    algorithm: str = "RS256"
    issuer: str = "gofr-sec"
    default_lifetime_seconds: int = 3600

    @classmethod
    def from_env(cls, prefix: str = _ENV_PREFIX) -> "SigningSettings":
        return cls(
            vault_path=os.getenv(f"{prefix}_SIGNING_VAULT_PATH"),
            algorithm=os.getenv(f"{prefix}_SIGNING_ALGORITHM", "RS256").upper(),
            issuer=os.getenv(f"{prefix}_TOKEN_ISSUER", "gofr-sec"),
            default_lifetime_seconds=int(
                os.getenv(f"{prefix}_TOKEN_DEFAULT_LIFETIME_S", "3600")
            ),
        )


@dataclass(frozen=True)
class CacheSettings:
    """Cache settings for verification keys and authorization decisions."""

    authz_ttl_seconds: int = 30
    public_key_ttl_seconds: int = 300

    @classmethod
    def from_env(cls, prefix: str = _ENV_PREFIX) -> "CacheSettings":
        return cls(
            authz_ttl_seconds=int(os.getenv(f"{prefix}_AUTHZ_CACHE_TTL_S", "30")),
            public_key_ttl_seconds=int(
                os.getenv(f"{prefix}_PUBLIC_KEY_CACHE_TTL_S", "300")
            ),
        )


def _env_with_global_fallback(prefix: str, suffix: str) -> str | None:
    return os.getenv(f"{prefix}_{suffix}") or os.getenv(f"GOFR_{suffix}")


@dataclass(frozen=True)
class VaultRepositorySettings:
    """Vault configuration used by gofr-sec persistence repositories."""

    url: str | None = None
    token: str | None = None
    role_id: str | None = None
    secret_id: str | None = None
    mount_point: str = "secret"
    path_prefix: str = "gofr/sec"
    timeout: int = 30
    namespace: str | None = None
    verify_ssl: bool = True

    @classmethod
    def from_env(cls, prefix: str = _ENV_PREFIX) -> "VaultRepositorySettings":
        verify_ssl_value = _env_with_global_fallback(prefix, "VAULT_VERIFY_SSL") or "true"
        timeout_value = _env_with_global_fallback(prefix, "VAULT_TIMEOUT") or "30"
        return cls(
            url=_env_with_global_fallback(prefix, "VAULT_URL"),
            token=_env_with_global_fallback(prefix, "VAULT_TOKEN"),
            role_id=_env_with_global_fallback(prefix, "VAULT_ROLE_ID"),
            secret_id=_env_with_global_fallback(prefix, "VAULT_SECRET_ID"),
            mount_point=_env_with_global_fallback(prefix, "VAULT_MOUNT") or "secret",
            path_prefix=_env_with_global_fallback(prefix, "VAULT_PATH_PREFIX") or "gofr/sec",
            timeout=int(timeout_value),
            namespace=_env_with_global_fallback(prefix, "VAULT_NAMESPACE"),
            verify_ssl=verify_ssl_value.lower() in {"true", "1", "yes"},
        )

    def is_configured(self) -> bool:
        has_token = bool(self.token)
        has_approle = bool(self.role_id and self.secret_id)
        return bool(self.url) and (has_token or has_approle)

    def to_vault_config(self) -> VaultConfig:
        if not self.is_configured():
            raise ValueError("Vault repository settings are incomplete")

        return VaultConfig(
            url=str(self.url),
            token=self.token,
            role_id=self.role_id,
            secret_id=self.secret_id,
            mount_point=self.mount_point,
            path_prefix=self.path_prefix,
            timeout=self.timeout,
            namespace=self.namespace,
            verify_ssl=self.verify_ssl,
        )


@dataclass(frozen=True)
class GofrSecServiceSettings:
    """gofr-sec-specific settings layered on shared GOFR settings."""

    core: Settings
    keycloak: KeycloakSettings
    bootstrap: BootstrapAdminSettings
    signing: SigningSettings
    cache: CacheSettings
    vault: VaultRepositorySettings


def get_settings(reload: bool = False, require_auth: bool = False) -> Settings:
    """Get or create the gofr-sec settings instance."""
    global _settings

    if _settings is None or reload:
        _settings = Settings.from_env(
            prefix=_ENV_PREFIX,
            require_auth=require_auth,
            project_root=_PROJECT_ROOT,
            default_mcp_port=DEFAULT_MCP_PORT,
            default_web_port=DEFAULT_WEB_PORT,
            default_mcpo_port=DEFAULT_MCPO_PORT,
        )
        _settings.resolve_defaults()
        _settings.validate()

    return _settings


def get_service_settings(
    reload: bool = False,
    require_auth: bool = False,
) -> GofrSecServiceSettings:
    """Get gofr-sec-specific settings layered on shared GOFR settings."""
    global _service_settings

    if _service_settings is None or reload:
        core = get_settings(reload=reload, require_auth=require_auth)
        _service_settings = GofrSecServiceSettings(
            core=core,
            keycloak=KeycloakSettings.from_env(_ENV_PREFIX),
            bootstrap=BootstrapAdminSettings.from_env(_ENV_PREFIX),
            signing=SigningSettings.from_env(_ENV_PREFIX),
            cache=CacheSettings.from_env(_ENV_PREFIX),
            vault=VaultRepositorySettings.from_env(_ENV_PREFIX),
        )

    return _service_settings


def reset_settings() -> None:
    """Reset the cached gofr-sec settings instance."""
    global _service_settings, _settings
    _settings = None
    _service_settings = None


__all__ = [
    "ServerSettings",
    "AuthSettings",
    "StorageSettings",
    "LogSettings",
    "Settings",
    "BootstrapAdminSettings",
    "CacheSettings",
    "GofrSecServiceSettings",
    "KeycloakSettings",
    "SigningSettings",
    "VaultRepositorySettings",
    "get_settings",
    "get_service_settings",
    "reset_settings",
    "Config",
    "get_default_storage_dir",
    "get_default_token_store_path",
    "DEFAULT_MCP_PORT",
    "DEFAULT_WEB_PORT",
    "DEFAULT_MCPO_PORT",
]
