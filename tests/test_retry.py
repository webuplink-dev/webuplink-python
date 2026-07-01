"""
Unit tests for idempotency-aware retry logic.

Verifies that the SDK:
  - Retries on connection errors (transport raises)
  - Retries on 500 with retry_after for observe-only requests
  - Does NOT retry when tools are involved (non-idempotent)
  - Does NOT retry on 4xx
  - Does NOT retry 429 even with retry_after (amplifies load)
  - Does NOT retry 500 without retry_after
  - Respects max_retries=0
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from webuplink import WebUplink, WebUplinkError
from webuplink._errors import APIConnectionError

BROWSE_OK = {
    "session_id": "s1",
    "url": "u",
    "title": "t",
    "summary": "s",
    "tools": [],
}


@respx.mock
def test_retries_on_connection_error() -> None:
    """Connection errors are always safe to retry (request never reached server)."""
    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("ECONNREFUSED")
        return httpx.Response(200, json=BROWSE_OK)

    respx.post("https://api.test.dev/v1/browse").mock(side_effect=side_effect)

    with patch("webuplink._client.sleep_sync"):  # Skip actual sleep
        client = WebUplink(api_key="k", base_url="https://api.test.dev", max_retries=3)
        result = client.browse("https://example.com")

    assert result.session_id == "s1"
    assert call_count == 3


@respx.mock
def test_retries_500_with_retry_after_for_observe() -> None:
    """Observe-only (no tools) + retry_after → should retry."""
    call_count = 0

    def side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return httpx.Response(
                500,
                json={"error": "INTERNAL_ERROR", "message": "Oops", "request_id": "r1", "retry_after": 0.01},
                headers={"x-request-id": "r1"},
            )
        return httpx.Response(200, json=BROWSE_OK)

    respx.post("https://api.test.dev/v1/browse").mock(side_effect=side_effect)

    with patch("webuplink._client.sleep_sync"):
        client = WebUplink(api_key="k", base_url="https://api.test.dev", max_retries=2)
        result = client.browse("https://example.com")

    assert result.session_id == "s1"
    assert call_count == 2


@respx.mock
def test_no_retry_with_tools() -> None:
    """Tool execution is non-idempotent — should NOT retry even with retry_after."""
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(
            500,
            json={"error": "INTERNAL_ERROR", "message": "Oops", "request_id": "r2", "retry_after": 5},
            headers={"x-request-id": "r2"},
        )
    )

    client = WebUplink(api_key="k", base_url="https://api.test.dev", max_retries=3)

    with pytest.raises(WebUplinkError):
        client.browse(session_id="s1", tool="place_order", params={"item": "laptop"})

    # Only 1 call — no retries
    assert len(respx.calls) == 1


@respx.mock
def test_no_retry_on_4xx() -> None:
    """4xx errors are client errors — never retry."""
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(
            400,
            json={"error": "INVALID_REQUEST", "message": "Bad request", "request_id": "r3"},
            headers={"x-request-id": "r3"},
        )
    )

    client = WebUplink(api_key="k", base_url="https://api.test.dev", max_retries=3)

    with pytest.raises(WebUplinkError):
        client.browse("https://example.com")

    assert len(respx.calls) == 1


@respx.mock
def test_no_retry_429_even_with_retry_after() -> None:
    """429 RATE_LIMITED must NOT be auto-retried even with retry_after."""
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(
            429,
            json={"error": "RATE_LIMITED", "message": "Rate limited", "retry_after": 5},
            headers={"x-request-id": "rl1"},
        )
    )

    client = WebUplink(api_key="k", base_url="https://api.test.dev", max_retries=3)

    with pytest.raises(WebUplinkError):
        client.browse("https://example.com")

    assert len(respx.calls) == 1


@respx.mock
def test_no_retry_500_without_retry_after() -> None:
    """500 without retry_after → not retryable."""
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(
            500,
            json={"error": "INTERNAL_ERROR", "message": "Oops", "request_id": "r4"},
            headers={"x-request-id": "r4"},
        )
    )

    client = WebUplink(api_key="k", base_url="https://api.test.dev", max_retries=3)

    with pytest.raises(WebUplinkError):
        client.browse("https://example.com")

    assert len(respx.calls) == 1


@respx.mock
def test_max_retries_zero() -> None:
    """max_retries=0 disables all retries on connection errors."""
    respx.post("https://api.test.dev/v1/browse").mock(side_effect=httpx.ConnectError("ECONNREFUSED"))

    client = WebUplink(api_key="k", base_url="https://api.test.dev", max_retries=0)

    with pytest.raises(APIConnectionError):
        client.browse("https://example.com")

    assert len(respx.calls) == 1
