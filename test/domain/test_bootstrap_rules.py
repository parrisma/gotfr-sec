"""Bootstrap planning tests for reserved admin initialization."""

from app.domain import RESERVED_ADMIN_GROUP
from app.repositories import InMemoryGroupMembershipRepository, InMemoryGroupRepository
from app.services import BootstrapService


def test_bootstrap_plan_deduplicates_subjects():
    service = BootstrapService(InMemoryGroupRepository(), InMemoryGroupMembershipRepository())

    plan = service.build_plan(["sub-1", " sub-2 ", "sub-1", ""])

    assert plan.trusted_admin_subs == ("sub-1", "sub-2")
    assert plan.reserved_groups[0].name == RESERVED_ADMIN_GROUP


def test_bootstrap_apply_is_idempotent():
    groups = InMemoryGroupRepository()
    memberships = InMemoryGroupMembershipRepository()
    service = BootstrapService(groups, memberships)

    service.apply_plan(["bootstrap-admin"])
    service.apply_plan(["bootstrap-admin"])

    assert groups.get(RESERVED_ADMIN_GROUP) is not None
    assert memberships.count_members(RESERVED_ADMIN_GROUP) == 1
    assert memberships.has_membership("bootstrap-admin", RESERVED_ADMIN_GROUP) is True