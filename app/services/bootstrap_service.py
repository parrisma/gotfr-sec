"""Bootstrap planning helpers for reserved admin initialization."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.models import GroupDefinition, UserGroupMembership
from app.domain.rules import RESERVED_ADMIN_GROUP, build_reserved_admin_group
from app.repositories.interfaces import GroupMembershipRepository, GroupRepository


def _normalize_subjects(subjects: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    for subject in subjects:
        value = subject.strip()
        if value and value not in seen:
            normalized.append(value)
            seen.add(value)
    return tuple(normalized)


@dataclass(frozen=True)
class BootstrapPlan:
    """The desired reserved groups and initial admin subjects."""

    reserved_groups: tuple[GroupDefinition, ...]
    trusted_admin_subs: tuple[str, ...]


class BootstrapService:
    """Build and apply reserved admin bootstrap state."""

    def __init__(
        self,
        group_repository: GroupRepository,
        membership_repository: GroupMembershipRepository,
    ) -> None:
        self._group_repository = group_repository
        self._membership_repository = membership_repository

    def build_plan(self, trusted_admin_subs: Iterable[str]) -> BootstrapPlan:
        return BootstrapPlan(
            reserved_groups=(build_reserved_admin_group(),),
            trusted_admin_subs=_normalize_subjects(trusted_admin_subs),
        )

    def apply_plan(self, trusted_admin_subs: Iterable[str]) -> BootstrapPlan:
        plan = self.build_plan(trusted_admin_subs)

        for group in plan.reserved_groups:
            if self._group_repository.get(group.name) is None:
                self._group_repository.upsert(group)

        for keycloak_sub in plan.trusted_admin_subs:
            if not self._membership_repository.has_membership(
                keycloak_sub, RESERVED_ADMIN_GROUP
            ):
                self._membership_repository.add(
                    UserGroupMembership(
                        keycloak_sub=keycloak_sub,
                        group_name=RESERVED_ADMIN_GROUP,
                    )
                )

        return plan