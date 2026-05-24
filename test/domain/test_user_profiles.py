"""Tests for pure user and in-memory repository behavior."""

from app.domain.models import AuditEvent, IssuedTokenRecord, UserProfile
from app.repositories import (
    InMemoryAuditEventRepository,
    InMemoryTokenRepository,
    InMemoryUserProfileRepository,
)


def test_user_profile_repository_round_trip():
    repository = InMemoryUserProfileRepository()
    profile = UserProfile(keycloak_sub="kc-user-1", display_name="Test User")

    repository.upsert(profile)

    assert repository.is_registered("kc-user-1") is True
    assert repository.get("kc-user-1") == profile


def test_token_repository_filters_by_owner():
    repository = InMemoryTokenRepository()
    token_a = IssuedTokenRecord(
        token_id="token-a",
        owner_sub="kc-user-1",
        granted_groups=("plot.read",),
    )
    token_b = IssuedTokenRecord(
        token_id="token-b",
        owner_sub="kc-user-2",
        granted_groups=("plot.write",),
    )
    repository.upsert(token_a)
    repository.upsert(token_b)

    assert repository.list_for_user("kc-user-1") == [token_a]


def test_audit_repository_appends_events():
    repository = InMemoryAuditEventRepository()
    event = AuditEvent(event_type="bootstrap.applied", actor_sub="bootstrap-admin")

    repository.append(event)

    assert repository.list_all() == [event]