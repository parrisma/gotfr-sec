"""Runtime authorization services for GOFR service consumers."""

from __future__ import annotations

from datetime import datetime

from app.domain.models import AuditEvent, AuthorizationDecision, AuthorizationRequest, utc_now
from app.repositories.interfaces import AuditEventRepository, TokenRepository
from app.services.token_service import TokenSigner


class RuntimeAuthorizationService:
    """Return public verification keys and yes-or-no runtime decisions."""

    def __init__(
        self,
        token_repository: TokenRepository,
        audit_repository: AuditEventRepository,
    ) -> None:
        self._token_repository = token_repository
        self._audit_repository = audit_repository

    def get_public_key_document(self, token_signer: TokenSigner) -> dict[str, object]:
        return token_signer.public_key_document()

    def authorize(
        self,
        authorization_request: AuthorizationRequest,
        *,
        correlation_id: str | None = None,
        now: datetime | None = None,
    ) -> AuthorizationDecision:
        allowed = False
        current_time = now or utc_now()
        try:
            record = self._token_repository.get(authorization_request.token_id)
            if record is not None:
                required_permission = (
                    authorization_request.requested_group
                    or authorization_request.requested_resource
                )
                allowed = bool(
                    required_permission
                    and record.owner_sub == authorization_request.owner_sub
                    and record.status == "active"
                    and (record.expires_at is None or current_time < record.expires_at)
                    and required_permission in record.granted_groups
                )
        except Exception:
            self._audit_repository.append(
                AuditEvent(
                    event_type="runtime.authorize",
                    actor_sub=authorization_request.owner_sub,
                    subject_sub=authorization_request.owner_sub,
                    group_name=authorization_request.requested_group,
                    resource=authorization_request.requested_resource,
                    token_id=authorization_request.token_id,
                    correlation_id=correlation_id,
                    result="failure",
                )
            )
            raise

        self._audit_repository.append(
            AuditEvent(
                event_type="runtime.authorize",
                actor_sub=authorization_request.owner_sub,
                subject_sub=authorization_request.owner_sub,
                group_name=authorization_request.requested_group,
                resource=authorization_request.requested_resource,
                token_id=authorization_request.token_id,
                correlation_id=correlation_id,
                result="allow" if allowed else "deny",
            )
        )
        return AuthorizationDecision(allowed=allowed)