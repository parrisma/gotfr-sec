"""Schemas for runtime verification-key and authorization APIs."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class RuntimeAuthorizationRequestSchema(BaseModel):
    token_id: str
    owner_sub: str
    group: str | None = None
    resource: str | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "RuntimeAuthorizationRequestSchema":
        token_id = self.token_id.strip()
        owner_sub = self.owner_sub.strip()
        group = self.group.strip() if self.group and self.group.strip() else None
        resource = self.resource.strip() if self.resource and self.resource.strip() else None

        if not token_id:
            raise ValueError("token_id is required")
        if not owner_sub:
            raise ValueError("owner_sub is required")
        if bool(group) == bool(resource):
            raise ValueError("provide exactly one of group or resource")

        self.token_id = token_id
        self.owner_sub = owner_sub
        self.group = group
        self.resource = resource
        return self


class RuntimeAuthorizationResponse(BaseModel):
    allowed: bool