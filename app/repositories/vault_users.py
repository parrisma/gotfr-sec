"""Vault-backed repositories for GOFR user profiles."""

from __future__ import annotations

from datetime import datetime, timezone

from gofr_common.auth.backends import VaultClient

from app.domain.models import UserProfile
from app.repositories.vault_paths import VaultPathLayout


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _serialize_profile(profile: UserProfile) -> dict[str, str | None]:
    return {
        "keycloak_sub": profile.keycloak_sub,
        "registered_at": profile.registered_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
        "display_name": profile.display_name,
        "email": profile.email,
    }


def _deserialize_profile(data: dict[str, str | None]) -> UserProfile:
    registered_at = _parse_datetime(data.get("registered_at"))
    updated_at = _parse_datetime(data.get("updated_at"))
    fallback = datetime.now(timezone.utc)
    return UserProfile(
        keycloak_sub=str(data["keycloak_sub"]),
        registered_at=registered_at or fallback,
        updated_at=updated_at or fallback,
        display_name=data.get("display_name"),
        email=data.get("email"),
    )


def list_known_user_ids(client: VaultClient, paths: VaultPathLayout) -> list[str]:
    """List user IDs that exist anywhere under the users prefix."""
    keys = client.list_secrets(paths.users_root())
    return sorted({key.rstrip("/") for key in keys if key.rstrip("/")})


class VaultUserRepository:
    """Vault-backed repository for user profiles."""

    def __init__(self, client: VaultClient, paths: VaultPathLayout | None = None) -> None:
        self._client = client
        self._paths = paths or VaultPathLayout()

    def get(self, keycloak_sub: str) -> UserProfile | None:
        data = self._client.read_secret(self._paths.user_profile_path(keycloak_sub))
        if data is None:
            return None
        return _deserialize_profile(data)

    def upsert(self, profile: UserProfile) -> UserProfile:
        self._client.write_secret(
            self._paths.user_profile_path(profile.keycloak_sub),
            _serialize_profile(profile),
        )
        return profile

    def is_registered(self, keycloak_sub: str) -> bool:
        return self._client.secret_exists(self._paths.user_profile_path(keycloak_sub))