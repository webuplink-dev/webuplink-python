"""
Typed exception hierarchy for WebUplink API errors.

All non-2xx responses from the API are raised as WebUplinkError instances,
preserving the machine-readable error code, HTTP status, and request ID
for support correlation.

Subclasses provide convenient catch targets for the most common patterns:
  - AuthenticationError (401)
  - RateLimitError (429)
  - APIConnectionError (network/transport failures)
"""

from __future__ import annotations

from typing import Any


class WebUplinkError(Exception):
    """Base error for all WebUplink API errors."""

    code: str
    """Machine-readable error code (e.g. ``QUOTA_EXCEEDED``, ``SESSION_NOT_FOUND``)."""

    message: str
    """Human-readable error message from the API."""

    status_code: int
    """HTTP status code from the API response."""

    request_id: str
    """Unique request ID from ``x-request-id`` header — cite in support tickets."""

    retryable: bool
    """Whether the SDK considered this error safe to retry automatically."""

    retry_after: float | None
    """Seconds to wait before retrying (from ``retry_after`` in response body)."""

    details: Any | None
    """Additional error details from the API response, if any."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        request_id: str = "unknown",
        retryable: bool = False,
        retry_after: float | None = None,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        self.retryable = retryable
        self.retry_after = retry_after
        self.details = details

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"code={self.code!r}, "
            f"status_code={self.status_code}, "
            f"request_id={self.request_id!r}, "
            f"message={self.message!r}"
            f")"
        )


class AuthenticationError(WebUplinkError):
    """Raised on 401 Unauthorized — invalid or missing API key."""


class RateLimitError(WebUplinkError):
    """Raised on 429 Too Many Requests — rate limited or quota exceeded."""


class APIConnectionError(WebUplinkError):
    """Raised when the SDK cannot reach the API (network/transport failure)."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(
            message,
            code="CONNECTION_ERROR",
            status_code=0,
            request_id="unknown",
            retryable=True,
        )
        self.__cause__ = cause
