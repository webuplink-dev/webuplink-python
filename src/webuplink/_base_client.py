"""
Shared HTTP logic for both sync and async clients.

This module contains all request construction, response parsing, error
mapping, usage header extraction, and retry logic.  The ``WebUplink``
and ``AsyncWebUplink`` classes delegate to these functions so the
logic exists in exactly one place.

Retry semantics match the TypeScript SDK exactly:
  - API errors with ``retry_after``: sleep for ``retry_after`` seconds
  - Connection errors: linear backoff (1s × attempt)
  - Never retry 429 (amplifies load)
  - Never retry tool execution (non-idempotent)
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from webuplink._constants import USER_AGENT
from webuplink._errors import (
    AuthenticationError,
    RateLimitError,
    WebUplinkError,
)
from webuplink._types import BrowseResult, HealthResult, Usage, UsageResponse

DEFAULT_RETRY_DELAY_S = 5.0
"""Seconds to wait before retrying when the server omits ``retry_after``."""

# ── Header Construction ──────────────────────────────────────────


def make_headers(api_key: str) -> dict[str, str]:
    """Build the default request headers."""
    return {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
    }


# ── Response Parsing ─────────────────────────────────────────────


def parse_browse_response(response: httpx.Response) -> BrowseResult:
    """Deserialize a successful browse response + usage headers."""
    data = response.json()
    usage = _parse_usage_headers(response)
    return BrowseResult(**data, usage=usage)


def parse_health_response(response: httpx.Response) -> HealthResult:
    """Deserialize a successful health response."""
    return HealthResult(**response.json())


def parse_usage_response(response: httpx.Response) -> UsageResponse:
    """Deserialize a successful usage response."""
    return UsageResponse(**response.json())


def _parse_usage_headers(response: httpx.Response) -> Usage | None:
    """Extract ``X-Usage-*`` headers into a ``Usage`` model, or ``None``."""
    count = response.headers.get("x-usage-action-count")
    limit = response.headers.get("x-usage-action-limit")
    period = response.headers.get("x-usage-period-start")

    if not count or not limit or not period:
        return None

    return Usage(
        action_count=int(count),
        action_limit=int(limit),
        period_start=period,
    )


# ── Error Parsing ────────────────────────────────────────────────


def parse_error_response(response: httpx.Response) -> WebUplinkError:
    """Map a non-2xx ``httpx.Response`` to a ``WebUplinkError`` (or subclass)."""
    request_id = response.headers.get("x-request-id", "unknown")

    try:
        data: dict[str, Any] = response.json()
    except Exception:
        # Non-JSON body (e.g. 502 from load balancer)
        return _create_error_from_status(
            response.status_code,
            response.reason_phrase or f"HTTP {response.status_code}",
            code="INTERNAL_ERROR",
            status_code=response.status_code,
            request_id=request_id,
        )

    code = data.get("error", "INTERNAL_ERROR")
    message = data.get("message", response.reason_phrase or f"HTTP {response.status_code}")
    retry_after_raw = data.get("retry_after")
    details = data.get("details")

    # Retryability: the server sets retry_after for transient issues.
    # 429 (RATE_LIMITED / QUOTA_EXCEEDED) carries retry_after but
    # auto-retrying a throttle just amplifies load — never retry them.
    retryable = (
        response.status_code != 429
        and retry_after_raw is not None
        and float(retry_after_raw) > 0
    )

    return _create_error_from_status(
        response.status_code,
        message,
        code=code,
        status_code=response.status_code,
        request_id=request_id,
        retryable=retryable,
        retry_after=float(retry_after_raw) if retry_after_raw is not None else None,
        details=details,
    )


def _create_error_from_status(
    status: int,
    message: str,
    **kwargs: Any,
) -> WebUplinkError:
    """Map HTTP status to the most specific error subclass."""
    if status == 401:
        return AuthenticationError(message, **kwargs)
    if status == 429:
        return RateLimitError(message, **kwargs)
    return WebUplinkError(message, **kwargs)


# ── Retry Logic ──────────────────────────────────────────────────


def should_retry(
    error: WebUplinkError,
    *,
    attempt: int,
    max_retries: int,
    has_tools: bool,
) -> bool:
    """Decide whether a failed request should be retried.

    Rules (matching the TypeScript SDK exactly):
      1. Must have retries remaining (``attempt < 1 + max_retries``)
      2. The error must be marked retryable by ``parse_error_response``
      3. Tool execution is never retried (non-idempotent)
    """
    if attempt >= 1 + max_retries:
        return False
    if has_tools:
        return False
    return error.retryable


def get_retry_delay(error: WebUplinkError) -> float:
    """Return the delay (in seconds) before retrying an API error."""
    return error.retry_after if error.retry_after is not None else DEFAULT_RETRY_DELAY_S


def get_connection_retry_delay(attempt: int) -> float:
    """Return the delay (in seconds) before retrying a connection error.

    Uses linear backoff: 1s × attempt (matching the TS SDK).
    """
    return 1.0 * attempt


def sleep_sync(seconds: float) -> None:
    """Blocking sleep for sync retry loops."""
    time.sleep(seconds)
