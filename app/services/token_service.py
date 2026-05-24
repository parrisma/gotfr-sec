"""Token signing and token lifecycle services for Phase 6."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from typing import Protocol
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
import jwt

from gofr_common.auth import VerifiedIdentity
from gofr_common.auth.backends import VaultClient

from app.domain.errors import (
    GroupNotFoundError,
    SigningKeyUnavailableError,
    TokenNotFoundError,
    UnregisteredUserError,
)
from app.domain.models import AuditEvent, IssuedTokenRecord, utc_now
from app.domain.rules import ensure_runtime_groups_allowed
from app.repositories.interfaces import (
    AuditEventRepository,
    GroupRepository,
    TokenRepository,
    UserProfileRepository,
)
from app.repositories.vault_paths import VaultPathLayout
from app.settings import SigningSettings


class TokenSigner(Protocol):
    def sign_token(
        self,
        *,
        token_id: str,
        owner_sub: str,
        issued_at: datetime,
        expires_at: datetime | None,
    ) -> str: ...

    def public_key_pem(self) -> str: ...


@dataclass(frozen=True)
class MintedTokenResult:
    """A newly minted token plus its canonical metadata record."""

    record: IssuedTokenRecord
    raw_token: str


@dataclass(frozen=True)
class _LoadedSigningMaterial:
    private_key_pem: str
    public_key_pem: str
    kid: str | None


class StaticTokenSigner:
    """In-memory token signer used by tests and non-Vault callers."""

    def __init__(
        self,
        private_key_pem: bytes | str,
        *,
        algorithm: str = "RS256",
        issuer: str = "gofr-sec",
        key_id: str | None = None,
    ) -> None:
        raw_private_key = (
            private_key_pem.decode("ascii") if isinstance(private_key_pem, bytes) else private_key_pem
        )
        private_key = serialization.load_pem_private_key(
            raw_private_key.encode("ascii"),
            password=None,
        )
        public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

        self._private_key_pem = raw_private_key
        self._public_key_pem = public_key_pem
        self._algorithm = algorithm
        self._issuer = issuer
        self._key_id = key_id

    def sign_token(
        self,
        *,
        token_id: str,
        owner_sub: str,
        issued_at: datetime,
        expires_at: datetime | None,
    ) -> str:
        claims: dict[str, object] = {
            "jti": token_id,
            "sub": owner_sub,
            "iss": self._issuer,
            "iat": int(issued_at.timestamp()),
            "nbf": int(issued_at.timestamp()),
        }
        if expires_at is not None:
            claims["exp"] = int(expires_at.timestamp())

        headers = {"kid": self._key_id} if self._key_id else None
        return jwt.encode(
            claims,
            self._private_key_pem,
            algorithm=self._algorithm,
            headers=headers,
        )

    def public_key_pem(self) -> str:
        return self._public_key_pem


class VaultTokenSigner:
    """Vault-backed token signer that loads key material from a single Vault path."""

    def __init__(
        self,
        vault_client: VaultClient,
        vault_path: str,
        *,
        algorithm: str = "RS256",
        issuer: str = "gofr-sec",
    ) -> None:
        self._vault_client = vault_client
        self._vault_path = vault_path
        self._algorithm = algorithm
        self._issuer = issuer

    def _load_signing_material(self) -> _LoadedSigningMaterial:
        secret = self._vault_client.read_secret(self._vault_path)
        if secret is None:
            raise SigningKeyUnavailableError(
                f"Signing key secret is missing from Vault: {self._vault_path}"
            )

        private_key_pem = secret.get("private_key_pem")
        if not isinstance(private_key_pem, str) or not private_key_pem.strip():
            raise SigningKeyUnavailableError(
                f"Signing key secret is invalid at Vault path: {self._vault_path}"
            )

        key_id = secret.get("kid")
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("ascii"),
            password=None,
        )
        public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        return _LoadedSigningMaterial(
            private_key_pem=private_key_pem,
            public_key_pem=public_key_pem,
            kid=key_id if isinstance(key_id, str) else None,
        )

    def sign_token(
        self,
        *,
        token_id: str,
        owner_sub: str,
        issued_at: datetime,
        expires_at: datetime | None,
    ) -> str:
        material = self._load_signing_material()
        claims: dict[str, object] = {
            "jti": token_id,
            "sub": owner_sub,
            "iss": self._issuer,
            "iat": int(issued_at.timestamp()),
            "nbf": int(issued_at.timestamp()),
        }
        if expires_at is not None:
            claims["exp"] = int(expires_at.timestamp())

        headers = {"kid": material.kid} if material.kid else None
        return jwt.encode(
            claims,
            material.private_key_pem,
            algorithm=self._algorithm,
            headers=headers,
        )

    def public_key_pem(self) -> str:
        return self._load_signing_material().public_key_pem


def build_token_signer(
    *,
    vault_client: VaultClient | None,
    paths: VaultPathLayout,
    settings: SigningSettings,
) -> TokenSigner | None:
    if vault_client is None:
        return None

    return VaultTokenSigner(
        vault_client,
        settings.vault_path or paths.signing_key_path(),
        algorithm=settings.algorithm,
        issuer=settings.issuer,
    )


class AdminTokenService:
    """Mint and manage GOFR runtime tokens through admin-only APIs."""

    def __init__(
        self,
        group_repository: GroupRepository,
        user_profile_repository: UserProfileRepository,
        token_repository: TokenRepository,
        audit_repository: AuditEventRepository,
        token_signer: TokenSigner,
        *,
        default_lifetime_seconds: int = 3600,
    ) -> None:
        self._group_repository = group_repository
        self._user_profile_repository = user_profile_repository
        self._token_repository = token_repository
        self._audit_repository = audit_repository
        self._token_signer = token_signer
        self._default_lifetime_seconds = default_lifetime_seconds

    def mint_token(
        self,
        *,
        owner_sub: str,
        groups: list[str] | tuple[str, ...],
        actor_sub: str,
        correlation_id: str | None = None,
        expires_in_seconds: int | None = None,
        now: datetime | None = None,
    ) -> MintedTokenResult:
        try:
            if not self._user_profile_repository.is_registered(owner_sub):
                raise UnregisteredUserError(f"Unknown target user: {owner_sub}")

            granted_groups = self._validate_groups(groups)
            lifetime_seconds = (
                self._default_lifetime_seconds
                if expires_in_seconds is None
                else expires_in_seconds
            )
            if lifetime_seconds <= 0:
                raise ValueError("Token expiry must be greater than zero seconds")

            issued_at = now or utc_now()
            expires_at = issued_at + timedelta(seconds=lifetime_seconds)
            token_id = uuid4().hex
            raw_token = self._token_signer.sign_token(
                token_id=token_id,
                owner_sub=owner_sub,
                issued_at=issued_at,
                expires_at=expires_at,
            )
            record = self._token_repository.upsert(
                IssuedTokenRecord(
                    token_id=token_id,
                    owner_sub=owner_sub,
                    granted_groups=granted_groups,
                    issued_at=issued_at,
                    expires_at=expires_at,
                    issued_by_sub=actor_sub,
                    jwt_hash=hashlib.sha256(raw_token.encode("ascii")).hexdigest(),
                )
            )
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="admin.token.mint",
                    actor_sub=actor_sub,
                    subject_sub=owner_sub,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        self._audit_repository.append(
            AuditEvent(
                event_type="admin.token.mint",
                actor_sub=actor_sub,
                subject_sub=owner_sub,
                token_id=record.token_id,
                correlation_id=correlation_id,
                result="success",
            )
        )
        return MintedTokenResult(record=record, raw_token=raw_token)

    def get_token(
        self,
        *,
        token_id: str,
        actor_sub: str,
        correlation_id: str | None = None,
    ) -> IssuedTokenRecord:
        try:
            record = self._get_token_or_raise(token_id)
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="admin.token.inspect",
                    actor_sub=actor_sub,
                    token_id=token_id,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        self._audit_repository.append(
            AuditEvent(
                event_type="admin.token.inspect",
                actor_sub=actor_sub,
                token_id=token_id,
                subject_sub=record.owner_sub,
                correlation_id=correlation_id,
                result="success",
            )
        )
        return record

    def revoke_token(
        self,
        *,
        token_id: str,
        actor_sub: str,
        correlation_id: str | None = None,
        now: datetime | None = None,
    ) -> IssuedTokenRecord:
        try:
            current = self._get_token_or_raise(token_id)
            if current.status == "revoked":
                revoked = current
            else:
                revoked = self._token_repository.upsert(
                    IssuedTokenRecord(
                        token_id=current.token_id,
                        owner_sub=current.owner_sub,
                        granted_groups=current.granted_groups,
                        status="revoked",
                        issued_at=current.issued_at,
                        expires_at=current.expires_at,
                        issued_by_sub=current.issued_by_sub,
                        jwt_hash=current.jwt_hash,
                        pending_reveal=current.pending_reveal,
                        revoked_at=now or utc_now(),
                    )
                )
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="admin.token.revoke",
                    actor_sub=actor_sub,
                    token_id=token_id,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        self._audit_repository.append(
            AuditEvent(
                event_type="admin.token.revoke",
                actor_sub=actor_sub,
                token_id=token_id,
                subject_sub=revoked.owner_sub,
                correlation_id=correlation_id,
                result="success",
            )
        )
        return revoked

    def _validate_groups(self, groups: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        normalized_groups = ensure_runtime_groups_allowed(groups)
        if not normalized_groups:
            raise ValueError("At least one runtime group is required")

        unique_groups: list[str] = []
        seen: set[str] = set()
        for group_name in normalized_groups:
            if group_name in seen:
                continue
            seen.add(group_name)

            group = self._group_repository.get(group_name)
            if group is None or not group.is_active:
                raise GroupNotFoundError(f"Unknown group: {group_name}")
            unique_groups.append(group_name)
        return tuple(unique_groups)

    def _get_token_or_raise(self, token_id: str) -> IssuedTokenRecord:
        record = self._token_repository.get(token_id)
        if record is None:
            raise TokenNotFoundError(f"Unknown token: {token_id}")
        return record


class UserTokenService:
    """User-facing token metadata reads without raw-token reveal."""

    def __init__(
        self,
        token_repository: TokenRepository,
        audit_repository: AuditEventRepository,
    ) -> None:
        self._token_repository = token_repository
        self._audit_repository = audit_repository

    def list_self_tokens(
        self,
        identity: VerifiedIdentity,
        *,
        correlation_id: str | None = None,
    ) -> tuple[IssuedTokenRecord, ...]:
        try:
            tokens = tuple(
                sorted(
                    self._token_repository.list_for_user(identity.subject),
                    key=lambda record: record.issued_at,
                    reverse=True,
                )
            )
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="user.token.list",
                    actor_sub=identity.subject,
                    subject_sub=identity.subject,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        self._audit_repository.append(
            AuditEvent(
                event_type="user.token.list",
                actor_sub=identity.subject,
                subject_sub=identity.subject,
                correlation_id=correlation_id,
                result="success",
            )
        )
        return tokens