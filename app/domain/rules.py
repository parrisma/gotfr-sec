"""Pure domain rules and invariants for gofr-sec."""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.domain.errors import LastAdminRemovalError, ReservedGroupError
from app.domain.models import GroupDefinition

RESERVED_ADMIN_GROUP = "admin"
_GROUP_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")


def normalize_group_name(name: str) -> str:
    """Normalize and validate a GOFR group name."""
    normalized = name.strip().lower()
    if not normalized or not _GROUP_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(f"Invalid group name: {name!r}")
    return normalized


def is_reserved_group(name: str) -> bool:
    """Return True when the group is reserved by the control plane."""
    return normalize_group_name(name) == RESERVED_ADMIN_GROUP


def build_reserved_admin_group() -> GroupDefinition:
    """Return the canonical reserved admin group definition."""
    return GroupDefinition(
        name=RESERVED_ADMIN_GROUP,
        description="Reserved control-plane administrators",
        is_system=True,
        is_active=True,
    )


def ensure_can_delete_group(name: str) -> None:
    """Raise if the caller attempts to delete a reserved group."""
    if is_reserved_group(name):
        raise ReservedGroupError("The reserved admin group cannot be deleted")


def ensure_can_rename_group(current_name: str, new_name: str) -> None:
    """Raise if a rename would mutate the reserved admin group."""
    if is_reserved_group(current_name) or is_reserved_group(new_name):
        raise ReservedGroupError("The reserved admin group cannot be renamed")


def ensure_admin_membership_remains(member_count: int) -> None:
    """Raise if an operation would leave the reserved admin group empty."""
    if member_count <= 0:
        raise LastAdminRemovalError("At least one admin membership must remain")


def ensure_runtime_groups_allowed(groups: Iterable[str]) -> tuple[str, ...]:
    """Return normalized runtime groups, rejecting reserved admin access."""
    normalized = tuple(normalize_group_name(group) for group in groups)
    if RESERVED_ADMIN_GROUP in normalized:
        raise ReservedGroupError(
            "The reserved admin group cannot be granted in runtime tokens"
        )
    return normalized