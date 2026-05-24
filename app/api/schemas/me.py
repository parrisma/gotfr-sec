"""Schemas for self-service registration and profile APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class MeRegisterResponse(BaseModel):
    keycloak_sub: str
    display_name: str | None = None
    email: str | None = None
    registered_at: datetime
    updated_at: datetime
    registration_status: Literal["created", "refreshed"]


class MeProfileResponse(BaseModel):
    keycloak_sub: str
    is_registered: bool
    display_name: str | None = None
    email: str | None = None
    registered_at: datetime | None = None
    updated_at: datetime | None = None
    groups: list[str]


class MeTokenResponse(BaseModel):
    token_id: str
    granted_groups: list[str]
    status: Literal["active", "revoked"]
    issued_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    issued_by_sub: str | None = None