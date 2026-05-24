"""Audit event sinks for gofr-sec."""

from __future__ import annotations

import logging

from app.domain.models import AuditEvent


class LoggingAuditEventRepository:
    """Simple audit sink that logs events and keeps an in-memory copy."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("gofr-sec.audit")
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        self._logger.info(
            "audit_event",
            extra={
                "event_type": event.event_type,
                "actor_sub": event.actor_sub,
                "subject_sub": event.subject_sub,
                "group_name": event.group_name,
                "token_id": event.token_id,
                "resource": event.resource,
                "correlation_id": event.correlation_id,
                "result": event.result,
                "occurred_at": event.occurred_at.isoformat(),
            },
        )
        return event

    def list_all(self) -> list[AuditEvent]:
        return list(self._events)