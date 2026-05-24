"""Integration tests for the canonical Vault path layout used by gofr-sec."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models import GroupDefinition, IssuedTokenRecord, UserProfile
from app.repositories import (
    VaultGroupRepository,
    VaultPathLayout,
    VaultTokenRepository,
    VaultUserRepository,
)

pytestmark = pytest.mark.vault_integration


def test_vault_path_layout_writes_expected_locations(vault_client):
    prefix = f"gofr/sec-tests/{uuid4().hex[:8]}"
    paths = VaultPathLayout(path_prefix=prefix)

    user_repo = VaultUserRepository(vault_client, paths)
    group_repo = VaultGroupRepository(vault_client, paths)
    token_repo = VaultTokenRepository(vault_client, paths)

    user_repo.upsert(UserProfile(keycloak_sub="user-1"))
    group_repo.upsert(GroupDefinition(name="plot.read", description="Read plots"))
    token_repo.upsert(
        IssuedTokenRecord(
            token_id="token-1",
            owner_sub="user-1",
            granted_groups=("plot.read",),
        )
    )

    assert vault_client.secret_exists(paths.user_profile_path("user-1")) is True
    assert vault_client.secret_exists(paths.group_definition_path("plot.read")) is True
    assert vault_client.secret_exists(paths.token_path("token-1")) is True
    assert vault_client.secret_exists(paths.user_token_path("user-1", "token-1")) is True
    assert vault_client.secret_exists(paths.group_token_path("plot.read", "token-1")) is True