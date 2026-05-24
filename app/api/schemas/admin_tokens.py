"""Schemas for admin token minting and inspection APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CreateTokenRequest(BaseModel):
    groups: list[str]
    expires_in_seconds: int | None = None


class TokenMetadataResponse(BaseModel):
    token_id: str
    owner_sub: str
    granted_groups: list[str]
    status: Literal["active", "revoked"]
    issued_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    issued_by_sub: str | None = None


class MintedTokenResponse(TokenMetadataResponse):
    issued_token: str