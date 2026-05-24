"""Domain models, rules, and errors for gofr-sec."""

from app.domain.errors import (
    DomainError,
    GroupAlreadyExistsError,
    GroupMembershipNotFoundError,
    GroupNotFoundError,
    LastAdminRemovalError,
    ReservedGroupError,
    TokenRevealNotAllowedError,
    UnregisteredUserError,
)
from app.domain.models import (
    AuditEvent,
    AuthorizationDecision,
    AuthorizationRequest,
    GroupDefinition,
    IssuedTokenRecord,
    UserGroupMembership,
    UserProfile,
)
from app.domain.rules import (
    RESERVED_ADMIN_GROUP,
    build_reserved_admin_group,
    ensure_admin_membership_remains,
    ensure_can_delete_group,
    ensure_runtime_groups_allowed,
    normalize_group_name,
)

__all__ = [
    "AuditEvent",
    "AuthorizationDecision",
    "AuthorizationRequest",
    "DomainError",
    "GroupDefinition",
    "GroupAlreadyExistsError",
    "GroupMembershipNotFoundError",
    "GroupNotFoundError",
    "IssuedTokenRecord",
    "LastAdminRemovalError",
    "RESERVED_ADMIN_GROUP",
    "ReservedGroupError",
    "TokenRevealNotAllowedError",
    "UnregisteredUserError",
    "UserGroupMembership",
    "UserProfile",
    "build_reserved_admin_group",
    "ensure_admin_membership_remains",
    "ensure_can_delete_group",
    "ensure_runtime_groups_allowed",
    "normalize_group_name",
]