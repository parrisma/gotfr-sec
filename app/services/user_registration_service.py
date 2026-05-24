"""Service-layer logic for self-registration and user profile reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from gofr_common.auth import VerifiedIdentity

from app.domain.errors import UnregisteredUserError
from app.domain.models import AuditEvent, UserProfile, utc_now
from app.repositories.interfaces import (
    AuditEventRepository,
    GroupMembershipRepository,
    UserProfileRepository,
)


def _string_claim(claims: dict[str, object], name: str) -> str | None:
    value = claims.get(name)
    return value if isinstance(value, str) and value.strip() else None


@dataclass(frozen=True)
class RegistrationResult:
    """Result of an idempotent self-registration attempt."""

    profile: UserProfile
    registration_status: Literal["created", "refreshed"]


@dataclass(frozen=True)
class MeProfileView:
    """User-facing view returned by GET /v1/me."""

    keycloak_sub: str
    is_registered: bool
    display_name: str | None = None
    email: str | None = None
    registered_at: datetime | None = None
    updated_at: datetime | None = None
    groups: tuple[str, ...] = ()


class UserRegistrationService:
    """Register Keycloak users locally and return their GOFR profile state."""

    def __init__(
        self,
        user_profile_repository: UserProfileRepository,
        membership_repository: GroupMembershipRepository,
        audit_repository: AuditEventRepository,
    ) -> None:
        self._user_profile_repository = user_profile_repository
        self._membership_repository = membership_repository
        self._audit_repository = audit_repository

    def register_self(
        self,
        identity: VerifiedIdentity,
        *,
        correlation_id: str | None = None,
        now: datetime | None = None,
    ) -> RegistrationResult:
        existing = self._user_profile_repository.get(identity.subject)
        timestamp = now or utc_now()
        display_name = _string_claim(identity.claims, "name")
        email = _string_claim(identity.claims, "email")

        if existing is not None:
            display_name = display_name or existing.display_name
            email = email or existing.email

        profile = UserProfile(
            keycloak_sub=identity.subject,
            registered_at=existing.registered_at if existing is not None else timestamp,
            updated_at=timestamp,
            display_name=display_name,
            email=email,
        )

        try:
            saved_profile = self._user_profile_repository.upsert(profile)
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="user.registration",
                    actor_sub=identity.subject,
                    subject_sub=identity.subject,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        registration_status: Literal["created", "refreshed"] = (
            "created" if existing is None else "refreshed"
        )
        self._audit_repository.append(
            AuditEvent(
                event_type="user.registration",
                actor_sub=identity.subject,
                subject_sub=identity.subject,
                correlation_id=correlation_id,
                result=registration_status,
            )
        )
        return RegistrationResult(
            profile=saved_profile,
            registration_status=registration_status,
        )

    def get_self_profile(self, identity: VerifiedIdentity) -> MeProfileView:
        profile = self._user_profile_repository.get(identity.subject)
        groups = tuple(
            sorted(
                membership.group_name
                for membership in self._membership_repository.list_for_user(identity.subject)
            )
        )
        if profile is None:
            return MeProfileView(
                keycloak_sub=identity.subject,
                is_registered=False,
                groups=groups,
            )

        return MeProfileView(
            keycloak_sub=profile.keycloak_sub,
            is_registered=True,
            display_name=profile.display_name,
            email=profile.email,
            registered_at=profile.registered_at,
            updated_at=profile.updated_at,
            groups=groups,
        )

    def require_registered_user(self, keycloak_sub: str) -> UserProfile:
        profile = self._user_profile_repository.get(keycloak_sub)
        if profile is None:
            raise UnregisteredUserError(f"Unknown target user: {keycloak_sub}")
        return profile