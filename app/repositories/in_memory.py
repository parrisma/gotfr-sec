"""In-memory repository implementations for unit tests and planning."""

from __future__ import annotations

from app.domain.models import (
    AuditEvent,
    GroupDefinition,
    IssuedTokenRecord,
    UserGroupMembership,
    UserProfile,
)


class InMemoryUserProfileRepository:
    """In-memory user profile repository."""

    def __init__(self) -> None:
        self._profiles: dict[str, UserProfile] = {}

    def get(self, keycloak_sub: str) -> UserProfile | None:
        return self._profiles.get(keycloak_sub)

    def upsert(self, profile: UserProfile) -> UserProfile:
        self._profiles[profile.keycloak_sub] = profile
        return profile

    def is_registered(self, keycloak_sub: str) -> bool:
        return keycloak_sub in self._profiles


class InMemoryGroupRepository:
    """In-memory group definition repository."""

    def __init__(self) -> None:
        self._groups: dict[str, GroupDefinition] = {}

    def get(self, name: str) -> GroupDefinition | None:
        return self._groups.get(name)

    def upsert(self, group: GroupDefinition) -> GroupDefinition:
        self._groups[group.name] = group
        return group

    def list_all(self) -> list[GroupDefinition]:
        return list(self._groups.values())

    def delete(self, name: str) -> bool:
        return self._groups.pop(name, None) is not None


class InMemoryGroupMembershipRepository:
    """In-memory group membership repository."""

    def __init__(self) -> None:
        self._memberships: dict[tuple[str, str], UserGroupMembership] = {}

    def add(self, membership: UserGroupMembership) -> UserGroupMembership:
        key = (membership.keycloak_sub, membership.group_name)
        self._memberships[key] = membership
        return membership

    def remove(self, keycloak_sub: str, group_name: str) -> bool:
        key = (keycloak_sub, group_name)
        return self._memberships.pop(key, None) is not None

    def has_membership(self, keycloak_sub: str, group_name: str) -> bool:
        return (keycloak_sub, group_name) in self._memberships

    def list_for_user(self, keycloak_sub: str) -> list[UserGroupMembership]:
        return [
            membership
            for membership in self._memberships.values()
            if membership.keycloak_sub == keycloak_sub
        ]

    def list_for_group(self, group_name: str) -> list[UserGroupMembership]:
        return [
            membership
            for membership in self._memberships.values()
            if membership.group_name == group_name
        ]

    def count_members(self, group_name: str) -> int:
        return len(self.list_for_group(group_name))


class InMemoryTokenRepository:
    """In-memory token repository."""

    def __init__(self) -> None:
        self._tokens: dict[str, IssuedTokenRecord] = {}

    def get(self, token_id: str) -> IssuedTokenRecord | None:
        return self._tokens.get(token_id)

    def upsert(self, record: IssuedTokenRecord) -> IssuedTokenRecord:
        self._tokens[record.token_id] = record
        return record

    def list_for_user(self, owner_sub: str) -> list[IssuedTokenRecord]:
        return [
            record for record in self._tokens.values() if record.owner_sub == owner_sub
        ]


class InMemoryAuditEventRepository:
    """In-memory audit event sink."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def list_all(self) -> list[AuditEvent]:
        return list(self._events)