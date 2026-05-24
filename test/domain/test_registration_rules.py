"""Tests for self-registration service rules and invariants."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.errors import UnregisteredUserError
from app.repositories import (
    InMemoryAuditEventRepository,
    InMemoryGroupMembershipRepository,
    InMemoryUserProfileRepository,
)
from app.services import UserRegistrationService
from gofr_common.auth import VerifiedIdentity


def build_identity(
    *,
    subject: str = "kc-user-1",
    name: str | None = None,
    email: str | None = None,
) -> VerifiedIdentity:
    claims: dict[str, object] = {}
    if name is not None:
        claims["name"] = name
    if email is not None:
        claims["email"] = email

    return VerifiedIdentity(
        subject=subject,
        issuer="https://keycloak.example/realms/gofr",
        audience=("gofr-sec",),
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        claims=claims,
    )


def test_registration_service_creates_profile_without_memberships():
    profiles = InMemoryUserProfileRepository()
    memberships = InMemoryGroupMembershipRepository()
    audit = InMemoryAuditEventRepository()
    service = UserRegistrationService(profiles, memberships, audit)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    result = service.register_self(
        build_identity(name="Test User", email="user@example.com"),
        now=now,
    )

    assert result.registration_status == "created"
    assert result.profile.keycloak_sub == "kc-user-1"
    assert result.profile.display_name == "Test User"
    assert result.profile.email == "user@example.com"
    assert result.profile.registered_at == now
    assert memberships.list_for_user("kc-user-1") == []


def test_registration_service_is_idempotent_and_refreshes_profile():
    profiles = InMemoryUserProfileRepository()
    memberships = InMemoryGroupMembershipRepository()
    audit = InMemoryAuditEventRepository()
    service = UserRegistrationService(profiles, memberships, audit)
    first_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second_now = datetime(2026, 1, 2, tzinfo=timezone.utc)

    first = service.register_self(
        build_identity(name="Original User", email="first@example.com"),
        now=first_now,
    )
    second = service.register_self(
        build_identity(name="Updated User"),
        now=second_now,
    )

    assert first.registration_status == "created"
    assert second.registration_status == "refreshed"
    assert second.profile.registered_at == first_now
    assert second.profile.updated_at == second_now
    assert second.profile.display_name == "Updated User"
    assert second.profile.email == "first@example.com"
    assert [event.result for event in audit.list_all()] == ["created", "refreshed"]


def test_require_registered_user_raises_for_missing_profile():
    service = UserRegistrationService(
        InMemoryUserProfileRepository(),
        InMemoryGroupMembershipRepository(),
        InMemoryAuditEventRepository(),
    )

    with pytest.raises(UnregisteredUserError, match="Unknown target user: kc-user-404"):
        service.require_registered_user("kc-user-404")