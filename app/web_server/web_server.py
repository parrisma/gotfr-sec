from fastapi import FastAPI

from app.api.routes import (
    admin_groups_router,
    admin_memberships_router,
    admin_tokens_router,
    health_router,
    me_router,
)
from app.bootstrap import initialize_application_state


class GofrSecWebServer:
    """Minimal FastAPI surface for the gofr-sec bootstrap phase."""

    def __init__(self, version: str = "0.1.0"):
        self.app = FastAPI(
            title="gofr-sec",
            version=version,
            summary="Bootstrap security service for GOFR",
            description=(
                "Initial scaffold for the GOFR security service. "
                "This surface is intentionally minimal while the real auth, "
                "token, and authorization flows are implemented."
            ),
        )
        self.app.add_event_handler("startup", self._startup)
        self.app.add_event_handler("shutdown", self._shutdown)
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.include_router(admin_groups_router)
        self.app.include_router(admin_memberships_router)
        self.app.include_router(admin_tokens_router)
        self.app.include_router(me_router)
        self.app.include_router(health_router)

    def _startup(self) -> None:
        initialize_application_state(self.app)

    def _shutdown(self) -> None:
        access_token_verifier = getattr(self.app.state, "access_token_verifier", None)
        if access_token_verifier is not None:
            access_token_verifier.close()
