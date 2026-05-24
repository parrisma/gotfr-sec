"""Vault-backed repository for issued token metadata and indexes."""

from __future__ import annotations

from datetime import datetime, timezone

from gofr_common.auth.backends import VaultClient

from app.domain.models import IssuedTokenRecord
from app.repositories.vault_paths import VaultPathLayout


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _serialize_token(record: IssuedTokenRecord) -> dict[str, object]:
    return {
        "token_id": record.token_id,
        "owner_sub": record.owner_sub,
        "granted_groups": list(record.granted_groups),
        "status": record.status,
        "issued_at": record.issued_at.isoformat(),
        "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        "issued_by_sub": record.issued_by_sub,
        "jwt_hash": record.jwt_hash,
        "pending_reveal": record.pending_reveal,
        "revoked_at": record.revoked_at.isoformat() if record.revoked_at else None,
    }


def _deserialize_token(data: dict[str, object]) -> IssuedTokenRecord:
    issued_at = _parse_datetime(data.get("issued_at") if isinstance(data.get("issued_at"), str) else None)
    expires_at = _parse_datetime(data.get("expires_at") if isinstance(data.get("expires_at"), str) else None)
    revoked_at = _parse_datetime(data.get("revoked_at") if isinstance(data.get("revoked_at"), str) else None)
    raw_groups = data.get("granted_groups", [])
    groups = tuple(str(group) for group in raw_groups) if isinstance(raw_groups, list) else ()
    return IssuedTokenRecord(
        token_id=str(data["token_id"]),
        owner_sub=str(data["owner_sub"]),
        granted_groups=groups,
        status=str(data.get("status", "active")),
        issued_at=issued_at or datetime.now(timezone.utc),
        expires_at=expires_at,
        issued_by_sub=data.get("issued_by_sub") if isinstance(data.get("issued_by_sub"), str) or data.get("issued_by_sub") is None else str(data.get("issued_by_sub")),
        jwt_hash=data.get("jwt_hash") if isinstance(data.get("jwt_hash"), str) or data.get("jwt_hash") is None else str(data.get("jwt_hash")),
        pending_reveal=bool(data.get("pending_reveal", False)),
        revoked_at=revoked_at,
    )


class VaultTokenRepository:
    """Vault-backed repository for canonical token records and lookup indexes."""

    def __init__(self, client: VaultClient, paths: VaultPathLayout | None = None) -> None:
        self._client = client
        self._paths = paths or VaultPathLayout()

    def get(self, token_id: str) -> IssuedTokenRecord | None:
        data = self._client.read_secret(self._paths.token_path(token_id))
        if data is None:
            return None
        return _deserialize_token(data)

    def upsert(self, record: IssuedTokenRecord) -> IssuedTokenRecord:
        previous = self.get(record.token_id)

        self._client.write_secret(self._paths.token_path(record.token_id), _serialize_token(record))

        if previous and previous.owner_sub != record.owner_sub:
            self._client.delete_secret(
                self._paths.user_token_path(previous.owner_sub, previous.token_id),
                hard=True,
            )

        previous_groups = set(previous.granted_groups) if previous else set()
        current_groups = set(record.granted_groups)
        for group_name in previous_groups - current_groups:
            self._client.delete_secret(
                self._paths.group_token_path(group_name, record.token_id),
                hard=True,
            )

        self._client.write_secret(
            self._paths.user_token_path(record.owner_sub, record.token_id),
            {
                "token_id": record.token_id,
                "owner_sub": record.owner_sub,
                "status": record.status,
            },
        )

        for group_name in record.granted_groups:
            self._client.write_secret(
                self._paths.group_token_path(group_name, record.token_id),
                {
                    "token_id": record.token_id,
                    "group_name": group_name,
                    "owner_sub": record.owner_sub,
                    "status": record.status,
                },
            )

        return record

    def list_for_user(self, owner_sub: str) -> list[IssuedTokenRecord]:
        result: list[IssuedTokenRecord] = []
        for key in self._client.list_secrets(self._paths.user_tokens_root(owner_sub)):
            token_id = key.rstrip("/")
            if not token_id:
                continue
            record = self.get(token_id)
            if record is not None:
                result.append(record)
        return result