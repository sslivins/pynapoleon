"""Typed exception hierarchy for pynapoleon."""

from __future__ import annotations


class NapoleonError(Exception):
    """Base class for all pynapoleon errors."""


class NapoleonAuthError(NapoleonError):
    """Raised when authentication or token refresh fails permanently."""


class NapoleonConnectionError(NapoleonError):
    """Raised when the Ayla cloud is unreachable or returns a transport error."""


class NapoleonApiError(NapoleonError):
    """Raised when the Ayla cloud returns a non-success HTTP status.

    The :attr:`status` attribute carries the HTTP status code and
    :attr:`body` carries the (possibly truncated) response body for
    diagnostics. Authentication-related 401/403 are translated to
    :class:`NapoleonAuthError` instead.
    """

    def __init__(self, status: int, body: str, *, message: str | None = None) -> None:
        self.status = status
        self.body = body
        super().__init__(
            message or f"Ayla API call failed: HTTP {status}: {body[:512]}"
        )


class NapoleonNotFoundError(NapoleonError):
    """Raised when the requested device or property cannot be found."""


class NapoleonValueError(NapoleonError, ValueError):
    """Raised when a property is set to an invalid value."""
