"""Schemas for admin group-management APIs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CreateGroupRequest(BaseModel):
    name: str
    description: str | None = None


class GroupResponse(BaseModel):
    name: str
    description: str | None = None
    is_system: bool
    is_active: bool
    created_at: datetime