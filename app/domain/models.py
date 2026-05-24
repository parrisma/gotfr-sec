"""Pure domain models for gofr-sec."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class GroupDefinition:
    """A GOFR group definition."""

    name: str
    description: str | None = None
    is_system: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class UserProfile:
    """A registered GOFR user keyed by Keycloak sub."""

    keycloak_sub: str
    registered_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    display_name: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class UserGroupMembership:
    """A user's membership in a GOFR group."""

    keycloak_sub: str
    group_name: str
    granted_at: datetime = field(default_factory=utc_now)
    granted_by_sub: str | None = None


@dataclass(frozen=True)
class IssuedTokenRecord:
    """Canonical metadata for an issued GOFR JWT."""

    token_id: str
    owner_sub: str
    granted_groups: tuple[str, ...]
    status: Literal["active", "revoked"] = "active"
    issued_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    issued_by_sub: str | None = None
    jwt_hash: str | None = None
    pending_reveal: bool = False


@dataclass(frozen=True)
class AuthorizationRequest:
    """A runtime authorization request after local signature validation."""

    token_id: str
    owner_sub: str | None = None
    requested_group: str | None = None
    requested_resource: str | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    """A yes-or-no authorization result."""

    allowed: bool


@dataclass(frozen=True)
class AuditEvent:
    """An internal audit record for admin or runtime actions."""

    event_type: str
    actor_sub: str | None = None
    subject_sub: str | None = None
    group_name: str | None = None
    token_id: str | None = None
    resource: str | None = None
    correlation_id: str | None = None
    result: str = "success"
    occurred_at: datetime = field(default_factory=utc_now)