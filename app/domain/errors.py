"""Domain-specific error types for gofr-sec."""


class DomainError(RuntimeError):
    """Base class for domain-level failures."""


class ReservedGroupError(DomainError):
    """Raised when reserved-group invariants are violated."""


class LastAdminRemovalError(ReservedGroupError):
    """Raised when the last admin membership would be removed."""


class GroupAlreadyExistsError(DomainError):
    """Raised when a group create request reuses an existing name."""


class GroupNotFoundError(DomainError):
    """Raised when an operation references a missing GOFR group."""


class GroupMembershipNotFoundError(DomainError):
    """Raised when an operation references a missing user-group membership."""


class UnregisteredUserError(DomainError):
    """Raised when an operation requires a registered GOFR user."""


class TokenNotFoundError(DomainError):
    """Raised when an operation references a missing token record."""


class SigningKeyUnavailableError(DomainError):
    """Raised when token signing material is unavailable."""


class TokenRevealNotAllowedError(DomainError):
    """Raised when raw JWT reveal is disabled or unavailable."""