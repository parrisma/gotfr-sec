"""Route modules exposed by the gofr-sec API package."""

from app.api.routes.admin_groups import router as admin_groups_router
from app.api.routes.admin_memberships import router as admin_memberships_router
from app.api.routes.admin_tokens import router as admin_tokens_router
from app.api.routes.health import router as health_router
from app.api.routes.me import router as me_router
from app.api.routes.runtime import router as runtime_router

__all__ = [
	"admin_groups_router",
	"admin_memberships_router",
	"admin_tokens_router",
	"health_router",
	"me_router",
	"runtime_router",
]