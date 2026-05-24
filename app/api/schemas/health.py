"""Schemas for bootstrap health and status endpoints."""

from pydantic import BaseModel


class RootResponse(BaseModel):
    service: str
    status: str
    docs: str


class PingResponse(BaseModel):
    status: str


class StatusResponse(BaseModel):
    service: str
    phase: str
    proposal: str