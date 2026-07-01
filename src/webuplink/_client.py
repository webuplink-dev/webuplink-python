"""Sync and async client classes for WebUplink.

Usage::

    from webuplink import WebUplink

    client = WebUplink(api_key="wup_...")
    page = client.browse("https://example.com")
    print(page.tools)
    client.close_session(page.session_id)

For async usage::

    from webuplink import AsyncWebUplink

    async with AsyncWebUplink(api_key="wup_...") as client:
        page = await client.browse("https://example.com")
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self
from urllib.parse import quote

import httpx

from webuplink._base_client import (
    get_connection_retry_delay,
    get_retry_delay,
    make_headers,
    parse_browse_response,
    parse_error_response,
    parse_health_response,
    parse_usage_response,
    should_retry,
    sleep_sync,
)
from webuplink._constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    ENV_API_KEY,
)
from webuplink._errors import APIConnectionError, WebUplinkError
from webuplink._types import BrowseParams, BrowseResult, HealthResult, UsageResponse


def _resolve_api_key(api_key: str | None) -> str:
    """Resolve the API key from the argument or environment variable."""
    key = api_key or os.environ.get(ENV_API_KEY)
    if not key:
        msg = (
            "No API key provided.  Pass api_key= to the constructor "
            f"or set the {ENV_API_KEY} environment variable."
        )
        raise WebUplinkError(msg, code="MISSING_API_KEY", status_code=0, request_id="local")
    return key


def _normalize_base_url(base_url: str) -> str:
    """Strip trailing slashes from the base URL."""
    return base_url.rstrip("/")


def _build_browse_body(url_or_params: str | BrowseParams | None, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Normalize the browse() arguments into a JSON-serializable dict."""
    if isinstance(url_or_params, str):
        if kwargs:
            msg = (
                "browse() does not accept keyword arguments when a URL string is provided. "
                "Use session_id= for tool execution."
            )
            raise ValueError(msg)
        return {"url": url_or_params}
    if isinstance(url_or_params, BrowseParams):
        if kwargs:
            msg = "browse() does not accept keyword arguments when a BrowseParams model is provided."
            raise ValueError(msg)
        return url_or_params.model_dump(exclude_none=True)
    if url_or_params is None and kwargs:
        return BrowseParams(**kwargs).model_dump(exclude_none=True)
    msg = "browse() requires a URL string, BrowseParams, or keyword arguments."
    raise ValueError(msg)


def _has_tools(body: dict[str, Any]) -> bool:
    """Check if the request involves tool execution (non-idempotent)."""
    return bool(body.get("tool") or body.get("tools"))


# ── Sync Client ──────────────────────────────────────────────────


class WebUplink:
    """Synchronous client for the WebUplink API.

    Supports context manager usage::

        with WebUplink(api_key="wup_...") as client:
            page = client.browse("https://example.com")
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = _normalize_base_url(base_url)
        self._max_retries = max_retries
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=httpx.Timeout(timeout),
        )

    # ── Public Methods ───────────────────────────────────────────

    def browse(
        self,
        url_or_params: str | BrowseParams | None = None,
        /,
        **kwargs: Any,
    ) -> BrowseResult:
        """Browse a page or execute tools on a page.

        Args:
            url_or_params: A URL string (opens new session), a ``BrowseParams``
                model, or ``None`` (use keyword arguments instead).
            **kwargs: Keyword arguments forwarded to ``BrowseParams``.

        Returns:
            A ``BrowseResult`` with tools, summary, and optional results.

        Examples::

            # String shorthand
            page = client.browse("https://example.com")

            # Keyword arguments
            result = client.browse(
                session_id=page.session_id,
                tool="search",
                params={"query": "hello"},
            )
        """
        body = _build_browse_body(url_or_params, kwargs)
        response = self._request("POST", "/v1/browse", json=body, has_tools=_has_tools(body))
        return parse_browse_response(response)

    def close_session(self, session_id: str) -> None:
        """Close a browser session.

        Sessions auto-expire after 2 minutes of inactivity, but explicit
        cleanup is recommended to free resources immediately.
        """
        self._request("DELETE", f"/v1/session/{quote(session_id, safe='')}")

    def health(self) -> HealthResult:
        """Check API server health."""
        response = self._request("GET", "/health")
        return parse_health_response(response)

    def get_usage(self) -> UsageResponse:
        """Get current usage and billing information.

        Returns exact cross-instance usage for the authenticated tenant.
        Requires a full API key (playground tokens cannot access this endpoint).
        """
        response = self._request("GET", "/v1/usage")
        return parse_usage_response(response)

    def close(self) -> None:
        """Close the underlying HTTP client.  Safe to call multiple times."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ── Internal ─────────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        has_tools: bool = False,
    ) -> httpx.Response:
        """Execute an HTTP request with idempotency-aware retry."""
        url = f"{self._base_url}{path}"
        headers = make_headers(self._api_key)

        last_error: WebUplinkError | None = None
        max_attempts = 1 + self._max_retries

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._client.request(method, url, json=json, headers=headers)
            except httpx.HTTPError as exc:
                # Network/connection error — safe to retry regardless of
                # idempotency (request never reached the server).
                conn_err = APIConnectionError(str(exc), cause=exc)
                if attempt < max_attempts and self._max_retries > 0:
                    last_error = conn_err
                    sleep_sync(get_connection_retry_delay(attempt))
                    continue
                raise conn_err from exc

            if response.is_success:
                return response

            error = parse_error_response(response)

            if should_retry(error, attempt=attempt, max_retries=self._max_retries, has_tools=has_tools):
                last_error = error
                sleep_sync(get_retry_delay(error))
                continue

            raise error

        # Exhausted all retries
        raise last_error  # type: ignore[misc]


# ── Async Client ─────────────────────────────────────────────────


class AsyncWebUplink:
    """Asynchronous client for the WebUplink API.

    Supports async context manager::

        async with AsyncWebUplink(api_key="wup_...") as client:
            page = await client.browse("https://example.com")
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = _normalize_base_url(base_url)
        self._max_retries = max_retries
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
        )

    # ── Public Methods ───────────────────────────────────────────

    async def browse(
        self,
        url_or_params: str | BrowseParams | None = None,
        /,
        **kwargs: Any,
    ) -> BrowseResult:
        """Browse a page or execute tools on a page.  See ``WebUplink.browse``."""
        body = _build_browse_body(url_or_params, kwargs)
        response = await self._request("POST", "/v1/browse", json=body, has_tools=_has_tools(body))
        return parse_browse_response(response)

    async def close_session(self, session_id: str) -> None:
        """Close a browser session.  See ``WebUplink.close_session``."""
        await self._request("DELETE", f"/v1/session/{quote(session_id, safe='')}")

    async def health(self) -> HealthResult:
        """Check API server health."""
        response = await self._request("GET", "/health")
        return parse_health_response(response)

    async def get_usage(self) -> UsageResponse:
        """Get current usage and billing information.  See ``WebUplink.get_usage``."""
        response = await self._request("GET", "/v1/usage")
        return parse_usage_response(response)

    async def close(self) -> None:
        """Close the underlying HTTP client.  Safe to call multiple times."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── Internal ─────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        has_tools: bool = False,
    ) -> httpx.Response:
        """Execute an HTTP request with idempotency-aware retry."""
        url = f"{self._base_url}{path}"
        headers = make_headers(self._api_key)

        last_error: WebUplinkError | None = None
        max_attempts = 1 + self._max_retries

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.request(method, url, json=json, headers=headers)
            except httpx.HTTPError as exc:
                conn_err = APIConnectionError(str(exc), cause=exc)
                if attempt < max_attempts and self._max_retries > 0:
                    last_error = conn_err
                    await asyncio.sleep(get_connection_retry_delay(attempt))
                    continue
                raise conn_err from exc

            if response.is_success:
                return response

            error = parse_error_response(response)

            if should_retry(error, attempt=attempt, max_retries=self._max_retries, has_tools=has_tools):
                last_error = error
                await asyncio.sleep(get_retry_delay(error))
                continue

            raise error

        raise last_error  # type: ignore[misc]
