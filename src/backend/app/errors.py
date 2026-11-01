"""Domain-level exceptions.

The service layer raises these instead of HTTP errors so that business logic stays
transport-agnostic (no FastAPI imports). A single set of exception handlers in main.py
translates them to HTTP responses. This keeps services reusable (CLI, worker, tests)
and the HTTP concern at the edge.
"""


class DomainError(Exception):
    """Base class for expected, business-rule errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """A referenced entity does not exist. -> HTTP 404."""


class ConflictError(DomainError):
    """The request conflicts with current state (e.g. lost claim race). -> HTTP 409."""


class ForbiddenError(DomainError):
    """The caller is authenticated but not allowed this specific action. -> HTTP 403."""
