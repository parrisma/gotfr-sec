"""Domain tests for reserved group rules."""

import pytest

from app.domain import (
    RESERVED_ADMIN_GROUP,
    ReservedGroupError,
    build_reserved_admin_group,
    ensure_admin_membership_remains,
    ensure_can_delete_group,
    ensure_runtime_groups_allowed,
    normalize_group_name,
)


def test_build_reserved_admin_group():
    group = build_reserved_admin_group()

    assert group.name == RESERVED_ADMIN_GROUP
    assert group.is_system is True
    assert group.is_active is True


def test_reserved_admin_group_cannot_be_deleted():
    with pytest.raises(ReservedGroupError):
        ensure_can_delete_group("admin")


def test_runtime_groups_reject_admin():
    with pytest.raises(ReservedGroupError):
        ensure_runtime_groups_allowed(["plot.read", "admin"])


def test_group_name_normalization():
    assert normalize_group_name(" Plot.Read ") == "plot.read"


def test_admin_membership_must_remain():
    with pytest.raises(ReservedGroupError):
        ensure_admin_membership_remains(0)