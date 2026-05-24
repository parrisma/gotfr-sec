"""Integration tests for Vault-backed gofr-sec repositories."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models import (
    GroupDefinition,
    IssuedTokenRecord,
    UserGroupMembership,
    UserProfile,
)
from app.repositories import (
    VaultGroupMembershipRepository,
    VaultGroupRepository,
    VaultPathLayout,
    VaultTokenRepository,
    VaultUserRepository,
)

pytestmark = pytest.mark.vault_integration


@pytest.fixture
def vault_paths() -> VaultPathLayout:
    return VaultPathLayout(path_prefix=f"gofr/sec-tests/{uuid4().hex[:8]}")


def test_vault_user_repository_round_trip(vault_client, vault_paths):
    repository = VaultUserRepository(vault_client, vault_paths)
    profile = UserProfile(keycloak_sub="kc-user-1", display_name="Test User")

    repository.upsert(profile)

    assert repository.is_registered("kc-user-1") is True
    assert repository.get("kc-user-1") == profile


def test_vault_group_and_membership_repositories(vault_client, vault_paths):
    groups = VaultGroupRepository(vault_client, vault_paths)
    memberships = VaultGroupMembershipRepository(vault_client, vault_paths)

    groups.upsert(GroupDefinition(name="plot.read", description="Read plots"))
    memberships.add(
        UserGroupMembership(
            keycloak_sub="kc-admin-1",
            group_name="plot.read",
            granted_by_sub="bootstrap-admin",
        )
    )

    assert groups.get("plot.read") is not None
    assert memberships.has_membership("kc-admin-1", "plot.read") is True
    assert memberships.count_members("plot.read") == 1
    assert memberships.list_for_group("plot.read")[0].keycloak_sub == "kc-admin-1"


def test_vault_token_repository_indexes_by_user(vault_client, vault_paths):
    repository = VaultTokenRepository(vault_client, vault_paths)
    record = IssuedTokenRecord(
        token_id="token-abc",
        owner_sub="kc-user-1",
        granted_groups=("plot.read", "plot.write"),
    )

    repository.upsert(record)

    assert repository.get("token-abc") == record
    assert repository.list_for_user("kc-user-1") == [record]