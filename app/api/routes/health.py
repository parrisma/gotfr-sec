"""Bootstrap health and status routes for gofr-sec."""

from fastapi import APIRouter

from app.api.schemas import PingResponse, RootResponse, StatusResponse

router = APIRouter()


@router.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    return RootResponse(
        service="gofr-sec",
        status="ok",
        docs="/docs",
    )


@router.get("/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    return PingResponse(status="ok")


@router.get("/v1/status", response_model=StatusResponse)
async def status() -> StatusResponse:
    return StatusResponse(
        service="gofr-sec",
        phase="bootstrap",
        proposal="docs/gofr_sec_proposal.md",
    )