"""Schemas for admin membership-management APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class GroupMembershipResponse(BaseModel):
    keycloak_sub: str
    group_name: str
    granted_at: datetime
    granted_by_sub: str | None = None