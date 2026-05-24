"""Vault path layout helpers for gofr-sec persistence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VaultPathLayout:
    """Canonical Vault path layout for gofr-sec records and indexes."""

    path_prefix: str = "gofr/sec"

    def users_root(self) -> str:
        return f"{self.path_prefix}/users"

    def user_root(self, keycloak_sub: str) -> str:
        return f"{self.users_root()}/{keycloak_sub}"

    def user_profile_path(self, keycloak_sub: str) -> str:
        return f"{self.user_root(keycloak_sub)}/profile"

    def user_groups_path(self, keycloak_sub: str) -> str:
        return f"{self.user_root(keycloak_sub)}/groups"

    def user_tokens_root(self, keycloak_sub: str) -> str:
        return f"{self.user_root(keycloak_sub)}/tokens"

    def user_token_path(self, keycloak_sub: str, token_id: str) -> str:
        return f"{self.user_tokens_root(keycloak_sub)}/{token_id}"

    def groups_root(self) -> str:
        return f"{self.path_prefix}/groups"

    def group_root(self, group_name: str) -> str:
        return f"{self.groups_root()}/{group_name}"

    def group_definition_path(self, group_name: str) -> str:
        return f"{self.group_root(group_name)}/definition"

    def group_tokens_root(self, group_name: str) -> str:
        return f"{self.group_root(group_name)}/tokens"

    def group_token_path(self, group_name: str, token_id: str) -> str:
        return f"{self.group_tokens_root(group_name)}/{token_id}"

    def tokens_root(self) -> str:
        return f"{self.path_prefix}/tokens"

    def token_path(self, token_id: str) -> str:
        return f"{self.tokens_root()}/{token_id}"

    def signing_key_path(self) -> str:
        return f"{self.path_prefix}/signing/runtime"