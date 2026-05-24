"""Service-layer logic for admin group-management APIs."""

from __future__ import annotations

from app.domain.errors import (
    GroupAlreadyExistsError,
    GroupMembershipNotFoundError,
    GroupNotFoundError,
    ReservedGroupError,
    UnregisteredUserError,
)
from app.domain.models import AuditEvent, GroupDefinition, UserGroupMembership
from app.domain.rules import (
    RESERVED_ADMIN_GROUP,
    ensure_admin_membership_remains,
    is_reserved_group,
    normalize_group_name,
)
from app.repositories.interfaces import (
    AuditEventRepository,
    GroupMembershipRepository,
    GroupRepository,
    UserProfileRepository,
)


class AdminGroupService:
    """Create and manage GOFR groups through admin-only APIs."""

    def __init__(
        self,
        group_repository: GroupRepository,
        membership_repository: GroupMembershipRepository,
        user_profile_repository: UserProfileRepository,
        audit_repository: AuditEventRepository,
    ) -> None:
        self._group_repository = group_repository
        self._membership_repository = membership_repository
        self._user_profile_repository = user_profile_repository
        self._audit_repository = audit_repository

    def create_group(
        self,
        *,
        name: str,
        description: str | None,
        actor_sub: str,
        correlation_id: str | None = None,
    ) -> GroupDefinition:
        normalized_name = name.strip().lower()
        try:
            validated_name = normalize_group_name(name)
            if is_reserved_group(validated_name):
                raise ReservedGroupError(
                    "The reserved admin group cannot be created via admin APIs"
                )
            if self._group_repository.get(validated_name) is not None:
                raise GroupAlreadyExistsError(f"Group already exists: {validated_name}")

            cleaned_description = description.strip() if description and description.strip() else None
            group = GroupDefinition(name=validated_name, description=cleaned_description)
            created = self._group_repository.upsert(group)
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="admin.group.create",
                    actor_sub=actor_sub,
                    group_name=normalized_name or None,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        self._audit_repository.append(
            AuditEvent(
                event_type="admin.group.create",
                actor_sub=actor_sub,
                group_name=created.name,
                correlation_id=correlation_id,
                result="success",
            )
        )
        return created

    def add_membership(
        self,
        *,
        keycloak_sub: str,
        group_name: str,
        actor_sub: str,
        correlation_id: str | None = None,
    ) -> UserGroupMembership:
        normalized_group_name = group_name.strip().lower()
        try:
            validated_group_name = normalize_group_name(group_name)
            group = self._group_repository.get(validated_group_name)
            if group is None or not group.is_active:
                raise GroupNotFoundError(f"Unknown group: {validated_group_name}")
            if not self._user_profile_repository.is_registered(keycloak_sub):
                raise UnregisteredUserError(f"Unknown target user: {keycloak_sub}")

            existing_membership = self._find_membership(keycloak_sub, validated_group_name)
            if existing_membership is not None:
                membership = existing_membership
            else:
                membership = self._membership_repository.add(
                    UserGroupMembership(
                        keycloak_sub=keycloak_sub,
                        group_name=validated_group_name,
                        granted_by_sub=actor_sub,
                    )
                )
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="admin.group_membership.add",
                    actor_sub=actor_sub,
                    subject_sub=keycloak_sub,
                    group_name=normalized_group_name or None,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        self._audit_repository.append(
            AuditEvent(
                event_type="admin.group_membership.add",
                actor_sub=actor_sub,
                subject_sub=keycloak_sub,
                group_name=membership.group_name,
                correlation_id=correlation_id,
                result="success",
            )
        )
        return membership

    def remove_membership(
        self,
        *,
        keycloak_sub: str,
        group_name: str,
        actor_sub: str,
        correlation_id: str | None = None,
    ) -> None:
        normalized_group_name = group_name.strip().lower()
        try:
            validated_group_name = normalize_group_name(group_name)
            group = self._group_repository.get(validated_group_name)
            if group is None or not group.is_active:
                raise GroupNotFoundError(f"Unknown group: {validated_group_name}")

            existing_membership = self._find_membership(keycloak_sub, validated_group_name)
            if existing_membership is None:
                if not self._user_profile_repository.is_registered(keycloak_sub):
                    raise UnregisteredUserError(f"Unknown target user: {keycloak_sub}")
                raise GroupMembershipNotFoundError(
                    f"Group membership not found: {keycloak_sub} -> {validated_group_name}"
                )

            if validated_group_name == RESERVED_ADMIN_GROUP:
                ensure_admin_membership_remains(
                    self._membership_repository.count_members(RESERVED_ADMIN_GROUP) - 1
                )

            removed = self._membership_repository.remove(keycloak_sub, validated_group_name)
            if not removed:
                raise GroupMembershipNotFoundError(
                    f"Group membership not found: {keycloak_sub} -> {validated_group_name}"
                )
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="admin.group_membership.remove",
                    actor_sub=actor_sub,
                    subject_sub=keycloak_sub,
                    group_name=normalized_group_name or None,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        self._audit_repository.append(
            AuditEvent(
                event_type="admin.group_membership.remove",
                actor_sub=actor_sub,
                subject_sub=keycloak_sub,
                group_name=validated_group_name,
                correlation_id=correlation_id,
                result="success",
            )
        )

    def _find_membership(
        self,
        keycloak_sub: str,
        group_name: str,
    ) -> UserGroupMembership | None:
        for membership in self._membership_repository.list_for_user(keycloak_sub):
            if membership.group_name == group_name:
                return membership
        return None