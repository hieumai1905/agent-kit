"""Wave D1 canonical state foundation (stdlib-only, NOT a trusted write boundary)."""

from .coordinator import LocalCoordinator
from .errors import ConflictError, GateNotImplemented, InvalidTransition, StoreError

__all__ = ["LocalCoordinator", "ConflictError", "GateNotImplemented", "InvalidTransition", "StoreError"]
