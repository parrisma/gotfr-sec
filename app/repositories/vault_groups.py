"""Vault-backed repositories for group definitions and memberships."""

from __future__ import annotations

from datetime import datetime, timezone

from gofr_common.auth.backends import VaultClient

from app.domain.models import GroupDefinition, UserGroupMembership
from app.repositories.vault_paths import VaultPathLayout
from app.repositories.vault_users import list_known_user_ids


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _serialize_group(group: GroupDefinition) -> dict[str, str | bool | None]:
    return {
        "name": group.name,
        "description": group.description,
        "is_system": group.is_system,
        "is_active": group.is_active,
        "created_at": group.created_at.isoformat(),
    }


def _deserialize_group(data: dict[str, object]) -> GroupDefinition:
    created_at = _parse_datetime(data.get("created_at") if isinstance(data.get("created_at"), str) else None)
    return GroupDefinition(
        name=str(data["name"]),
        description=data.get("description") if isinstance(data.get("description"), str) or data.get("description") is None else str(data.get("description")),
        is_system=bool(data.get("is_system", False)),
        is_active=bool(data.get("is_active", True)),
        created_at=created_at or datetime.now(timezone.utc),
    )


def _serialize_membership(membership: UserGroupMembership) -> dict[str, str | None]:
    return {
        "keycloak_sub": membership.keycloak_sub,
        "group_name": membership.group_name,
        "granted_at": membership.granted_at.isoformat(),
        "granted_by_sub": membership.granted_by_sub,
    }


def _deserialize_membership(data: dict[str, str | None]) -> UserGroupMembership:
    granted_at = _parse_datetime(data.get("granted_at"))
    return UserGroupMembership(
        keycloak_sub=str(data["keycloak_sub"]),
        group_name=str(data["group_name"]),
        granted_at=granted_at or datetime.now(timezone.utc),
        granted_by_sub=data.get("granted_by_sub"),
    )


class VaultGroupRepository:
    """Vault-backed repository for group definitions."""

    def __init__(self, client: VaultClient, paths: VaultPathLayout | None = None) -> None:
        self._client = client
        self._paths = paths or VaultPathLayout()

    def get(self, name: str) -> GroupDefinition | None:
        data = self._client.read_secret(self._paths.group_definition_path(name))
        if data is None:
            return None
        return _deserialize_group(data)

    def upsert(self, group: GroupDefinition) -> GroupDefinition:
        self._client.write_secret(self._paths.group_definition_path(group.name), _serialize_group(group))
        return group

    def list_all(self) -> list[GroupDefinition]:
        result: list[GroupDefinition] = []
        for key in self._client.list_secrets(self._paths.groups_root()):
            group_name = key.rstrip("/")
            if not group_name:
                continue
            group = self.get(group_name)
            if group is not None:
                result.append(group)
        return result

    def delete(self, name: str) -> bool:
        return self._client.delete_secret(self._paths.group_definition_path(name), hard=True)


class VaultGroupMembershipRepository:
    """Vault-backed repository for user-to-group memberships."""

    def __init__(self, client: VaultClient, paths: VaultPathLayout | None = None) -> None:
        self._client = client
        self._paths = paths or VaultPathLayout()

    def _load_memberships(self, keycloak_sub: str) -> list[UserGroupMembership]:
        data = self._client.read_secret(self._paths.user_groups_path(keycloak_sub))
        if not data:
            return []
        raw_memberships = data.get("memberships", [])
        if not isinstance(raw_memberships, list):
            return []
        return [_deserialize_membership(item) for item in raw_memberships if isinstance(item, dict)]

    def _store_memberships(self, keycloak_sub: str, memberships: list[UserGroupMembership]) -> None:
        if not memberships:
            self._client.delete_secret(self._paths.user_groups_path(keycloak_sub), hard=True)
            return

        sorted_memberships = sorted(memberships, key=lambda membership: membership.group_name)
        self._client.write_secret(
            self._paths.user_groups_path(keycloak_sub),
            {
                "keycloak_sub": keycloak_sub,
                "memberships": [
                    _serialize_membership(membership) for membership in sorted_memberships
                ],
            },
        )

    def add(self, membership: UserGroupMembership) -> UserGroupMembership:
        memberships = [
            existing
            for existing in self._load_memberships(membership.keycloak_sub)
            if existing.group_name != membership.group_name
        ]
        memberships.append(membership)
        self._store_memberships(membership.keycloak_sub, memberships)
        return membership

    def remove(self, keycloak_sub: str, group_name: str) -> bool:
        memberships = self._load_memberships(keycloak_sub)
        updated = [membership for membership in memberships if membership.group_name != group_name]
        if len(updated) == len(memberships):
            return False
        self._store_memberships(keycloak_sub, updated)
        return True

    def has_membership(self, keycloak_sub: str, group_name: str) -> bool:
        return any(
            membership.group_name == group_name
            for membership in self._load_memberships(keycloak_sub)
        )

    def list_for_user(self, keycloak_sub: str) -> list[UserGroupMembership]:
        return self._load_memberships(keycloak_sub)

    def list_for_group(self, group_name: str) -> list[UserGroupMembership]:
        result: list[UserGroupMembership] = []
        for keycloak_sub in list_known_user_ids(self._client, self._paths):
            result.extend(
                membership
                for membership in self._load_memberships(keycloak_sub)
                if membership.group_name == group_name
            )
        return result

    def count_members(self, group_name: str) -> int:
        return len(self.list_for_group(group_name))