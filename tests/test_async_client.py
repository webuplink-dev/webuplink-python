"""
Unit tests for the async WebUplink client.

Mirrors test_client.py but exercises AsyncWebUplink with pytest-asyncio.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from webuplink import AsyncWebUplink, AuthenticationError
from webuplink._constants import USER_AGENT

BROWSE_OK = {
    "session_id": "s1",
    "url": "https://example.com",
    "title": "Example",
    "summary": "A test page",
    "tools": [{"name": "click_button", "description": "Click it", "params": []}],
}


@pytest.fixture
def client() -> AsyncWebUplink:
    return AsyncWebUplink(api_key="test-key", base_url="https://api.test.dev", max_retries=0)


@respx.mock
@pytest.mark.asyncio
async def test_browse_string(client: AsyncWebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    result = await client.browse("https://example.com")
    assert result.session_id == "s1"


@respx.mock
@pytest.mark.asyncio
async def test_browse_kwargs(client: AsyncWebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    await client.browse(session_id="s1", tool="search", params={"q": "test"})

    import json
    body = json.loads(respx.calls.last.request.content)
    assert body["tool"] == "search"


@respx.mock
@pytest.mark.asyncio
async def test_auth_header(client: AsyncWebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    await client.browse("https://example.com")
    assert respx.calls.last.request.headers["authorization"] == "Bearer test-key"


@respx.mock
@pytest.mark.asyncio
async def test_user_agent(client: AsyncWebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(return_value=httpx.Response(200, json=BROWSE_OK))
    await client.browse("https://example.com")
    assert respx.calls.last.request.headers["user-agent"] == USER_AGENT


@respx.mock
@pytest.mark.asyncio
async def test_usage_headers(client: AsyncWebUplink) -> None:
    headers = {
        "x-usage-action-count": "10",
        "x-usage-action-limit": "500",
        "x-usage-period-start": "2026-06-01T00:00:00Z",
    }
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(200, json=BROWSE_OK, headers=headers)
    )
    result = await client.browse("https://example.com")
    assert result.usage is not None
    assert result.usage.action_count == 10


@respx.mock
@pytest.mark.asyncio
async def test_close_session(client: AsyncWebUplink) -> None:
    respx.delete("https://api.test.dev/v1/session/s1").mock(
        return_value=httpx.Response(200, json={"status": "closed"})
    )
    await client.close_session("s1")


@respx.mock
@pytest.mark.asyncio
async def test_health(client: AsyncWebUplink) -> None:
    respx.get("https://api.test.dev/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "uptime_s": 42, "active_sessions": 0})
    )
    result = await client.health()
    assert result.status == "ok"


@respx.mock
@pytest.mark.asyncio
async def test_error_mapping(client: AsyncWebUplink) -> None:
    respx.post("https://api.test.dev/v1/browse").mock(
        return_value=httpx.Response(
            401,
            json={"error": "UNAUTHORIZED", "message": "Bad key", "request_id": "r1"},
            headers={"x-request-id": "r1"},
        )
    )
    with pytest.raises(AuthenticationError):
        await client.browse("https://example.com")


@respx.mock
@pytest.mark.asyncio
async def test_get_usage(client: AsyncWebUplink) -> None:
    usage_ok = {
        "plan": "pro",
        "actions": {"used": 4500, "limit": 5000},
        "period": {"start": "2026-06-01T00:00:00.000Z", "end": "2026-07-01T00:00:00.000Z"},
        "billing": {"has_subscription": True, "portal_url": "/v1/billing/portal"},
    }
    respx.get("https://api.test.dev/v1/usage").mock(
        return_value=httpx.Response(200, json=usage_ok)
    )
    result = await client.get_usage()
    assert result.plan == "pro"
    assert result.actions.used == 4500
    assert result.billing.has_subscription is True


@pytest.mark.asyncio
async def test_async_context_manager() -> None:
    async with AsyncWebUplink(api_key="k", base_url="https://test.dev", max_retries=0) as c:
        assert isinstance(c, AsyncWebUplink)
