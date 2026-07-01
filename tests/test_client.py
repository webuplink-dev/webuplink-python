"""
Unit tests for the sync WebUplink client.

Uses respx to mock httpx transport — no real network calls.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import httpx
import pytest
import respx

from webuplink import (
    AuthenticationError,
    BrowseParams,
    RateLimitError,
    WebUplink,
    WebUplinkError,
)
from webuplink._constants import USER_AGENT

# ── Fixtures ─────────────────────────────────────────────────────

BROWSE_OK = {
    "session_id": "s1",
    "url": "https://example.com",
    "title": "Example",
    "summary": "A test page",
    "tools": [{"name": "click_button", "description": "Click it", "params": []}],
}


@pytest.fixture
def client() -> WebUplink:
    return WebUplink(api_key="test-key", base_url="https://api.test.dev", max_retries=0)


# ── Constructor ──────────────────────────────────────────────────


def test_requires_api_key() -> None:
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("WEBUPLINK_API_KEY", None)
        with pytest.raises(WebUplinkError, match="No API key"):
            WebUplink(base_url="https://api.test.dev")


def test_resolves_api_key_from_env() -> None:
    with patch.dict(os.environ, {"WEBUPLINK_API_KEY": "env-key"}):
        c = WebUplink(base_url="https://api.test.dev", max_retries=0)
        assert c._api_key == "env-key"
        c.close()


def test_explicit_key_takes_precedence() -> None:
    with patch.dict(os.environ, {"WEBUPLINK_API_KEY": "env-key"}):
        c = WebUplink(api_key="explicit-key", base_url="https://api.test.dev", max_retries=0)
        assert c._api_key == "explicit-key"
        c.close()


def test_strips_trailing_slash() -> None:
    c = WebUplink(api_key="k", base_url="https://api.test.dev///", max_retries=0)
    assert c._base_url == "https://api.test.dev"
    c.close()


# ── browse() ─────────────────────────────────────────────────────


@respx.mock
def test_browse_string_shorthand(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    result = client.browse("https://example.com")
    assert result.session_id == "s1"
    assert result.tools[0].name == "click_button"

    req = respx.calls.last.request
    assert req.content == b'{"url":"https://example.com"}'


@respx.mock
def test_browse_kwargs(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    client.browse(session_id="s1", tool="search", params={"q": "test"})

    import json
    body = json.loads(respx.calls.last.request.content)
    assert body == {"session_id": "s1", "tool": "search", "params": {"q": "test"}}


@respx.mock
def test_browse_params_model(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    client.browse(BrowseParams(url="https://example.com"))

    import json
    body = json.loads(respx.calls.last.request.content)
    assert body == {"url": "https://example.com"}


def test_browse_string_rejects_kwargs(client: WebUplink) -> None:
    with pytest.raises(ValueError, match="does not accept keyword arguments when a URL string"):
        client.browse("https://example.com", tool="search")


def test_browse_model_rejects_kwargs(client: WebUplink) -> None:
    with pytest.raises(ValueError, match="does not accept keyword arguments when a BrowseParams"):
        client.browse(BrowseParams(url="https://example.com"), tool="search")


def test_browse_no_args_raises(client: WebUplink) -> None:
    with pytest.raises(ValueError, match="requires a URL string"):
        client.browse()


@respx.mock
def test_auth_header(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    client.browse("https://example.com")

    req = respx.calls.last.request
    assert req.headers["authorization"] == "Bearer test-key"


@respx.mock
def test_user_agent_header(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    client.browse("https://example.com")

    req = respx.calls.last.request
    assert req.headers["user-agent"] == USER_AGENT


@respx.mock
def test_usage_header_parsing(client: WebUplink) -> None:
    headers = {
        "x-usage-action-count": "5",
        "x-usage-action-limit": "1000",
        "x-usage-period-start": "2026-06-01T00:00:00.000Z",
    }
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(200, json=BROWSE_OK, headers=headers)
    )
    result = client.browse("https://example.com")

    assert result.usage is not None
    assert result.usage.action_count == 5
    assert result.usage.action_limit == 1000
    assert result.usage.period_start == "2026-06-01T00:00:00.000Z"


@respx.mock
def test_usage_absent(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    result = client.browse("https://example.com")
    assert result.usage is None


# ── close_session() ──────────────────────────────────────────────


@respx.mock
def test_close_session_path(client: WebUplink) -> None:
    respx.delete("https://api.test.dev/v1/session/session-123").mock(
        return_value=httpx.Response(200, json={"status": "closed"})
    )
    client.close_session("session-123")
    assert respx.calls.last.request.url == "https://api.test.dev/v1/session/session-123"


@respx.mock
def test_close_session_encodes_special_chars(client: WebUplink) -> None:
    respx.delete(url__regex=r".*/v1/session/.*").mock(
        return_value=httpx.Response(200, json={"status": "closed"})
    )
    client.close_session("session/with/slashes")
    assert "session%2Fwith%2Fslashes" in str(respx.calls.last.request.url)


# ── health() ─────────────────────────────────────────────────────


@respx.mock
def test_health(client: WebUplink) -> None:
    respx.get("https://api.test.dev/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "uptime_s": 100, "active_sessions": 0})
    )
    result = client.health()
    assert result.status == "ok"
    assert result.uptime_s == 100


# ── Error Handling ───────────────────────────────────────────────


@respx.mock
def test_error_mapping(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(
            404,
            json={"error": "SESSION_NOT_FOUND", "message": "Session not found", "request_id": "req-1"},
            headers={"x-request-id": "req-1"},
        )
    )
    with pytest.raises(WebUplinkError) as exc_info:
        client.browse("https://example.com")

    err = exc_info.value
    assert err.code == "SESSION_NOT_FOUND"
    assert err.status_code == 404
    assert err.request_id == "req-1"
    assert err.retryable is False


@respx.mock
def test_401_raises_auth_error(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(
            401,
            json={"error": "UNAUTHORIZED", "message": "Invalid API key", "request_id": "req-2"},
            headers={"x-request-id": "req-2"},
        )
    )
    with pytest.raises(AuthenticationError):
        client.browse("https://example.com")


@respx.mock
def test_429_raises_rate_limit_error(client: WebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(
            429,
            json={"error": "RATE_LIMITED", "message": "Rate limited", "request_id": "req-3", "retry_after": 5},
            headers={"x-request-id": "req-3"},
        )
    )
    with pytest.raises(RateLimitError) as exc_info:
        client.browse("https://example.com")

    assert exc_info.value.retry_after == 5.0
    assert exc_info.value.retryable is False  # 429 is never auto-retried


# ── get_usage() ──────────────────────────────────────────────────

USAGE_OK = {
    "plan": "builder",
    "actions": {"used": 142, "limit": 1000},
    "period": {"start": "2026-06-01T00:00:00.000Z", "end": "2026-07-01T00:00:00.000Z"},
    "billing": {"has_subscription": True, "portal_url": "/v1/billing/portal"},
}


@respx.mock
def test_get_usage(client: WebUplink) -> None:
    respx.get("https://api.test.dev/v1/usage").mock(
        return_value=httpx.Response(200, json=USAGE_OK)
    )
    result = client.get_usage()

    assert result.plan == "builder"
    assert result.actions.used == 142
    assert result.actions.limit == 1000
    assert result.period.start == "2026-06-01T00:00:00.000Z"
    assert result.period.end == "2026-07-01T00:00:00.000Z"
    assert result.billing.has_subscription is True
    assert result.billing.portal_url == "/v1/billing/portal"


@respx.mock
def test_get_usage_auth_error(client: WebUplink) -> None:
    respx.get("https://api.test.dev/v1/usage").mock(
        return_value=httpx.Response(
            401,
            json={"error": "UNAUTHORIZED", "message": "Invalid API key", "request_id": "req-u"},
            headers={"x-request-id": "req-u"},
        )
    )
    with pytest.raises(AuthenticationError):
        client.get_usage()


# ── Context Manager ──────────────────────────────────────────────


def test_context_manager() -> None:
    with WebUplink(api_key="k", base_url="https://test.dev", max_retries=0) as c:
        assert isinstance(c, WebUplink)
    # Should not raise on second close
    c.close()


def test_close_idempotent() -> None:
    c = WebUplink(api_key="k", base_url="https://test.dev", max_retries=0)
    c.close()
    c.close()  # Should not raise
