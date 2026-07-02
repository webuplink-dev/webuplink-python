"""
Pydantic models for WebUplink API request and response types.

These models provide typed, validated representations of all API
inputs and outputs.  Every field is documented and IDE-autocomplete
friendly.

Models use ``from __future__ import annotations`` so that ``X | Y``
union syntax works on Python 3.10 at runtime with Pydantic v2.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

# ── Tool Types ───────────────────────────────────────────────────


class ToolParam(BaseModel):
    """A single parameter accepted by a tool."""

    name: str
    """Machine-readable parameter name, e.g. ``section``, ``query``."""

    description: str
    """What values this parameter accepts."""


class Tool(BaseModel):
    """A callable tool discovered on a web page."""

    name: str
    """Machine-readable name, e.g. ``search_hotels``, ``filter_by_price``."""

    description: str
    """Human-readable description of what this tool does."""

    params: list[ToolParam]
    """Parameter definitions for this tool."""


class ToolResult(BaseModel):
    """Result of a single tool execution."""

    tool: str
    """Which tool was executed."""

    success: bool
    """Whether the tool completed successfully."""

    error: str | None = None
    """Error message if ``success`` is ``False``."""


class ToolExecution(BaseModel):
    """A single tool invocation in a batch request."""

    tool: str
    """Name of the tool to execute."""

    params: dict[str, Any]
    """Parameters to pass to the tool."""


# ── Browse Request ───────────────────────────────────────────────


class BrowseParams(BaseModel):
    """Parameters for a ``POST /v1/browse`` request.

    Users can also pass these as keyword arguments to ``client.browse()``
    instead of constructing this model explicitly.
    """

    url: str | None = None
    """URL to browse.  Creates a new session.  Mutually exclusive with ``session_id``."""

    session_id: str | None = None
    """Existing session ID.  Mutually exclusive with ``url``."""

    tool: str | None = None
    """Single tool to execute (requires ``session_id``)."""

    params: dict[str, Any] | None = None
    """Parameters for the single ``tool``."""

    tools: list[ToolExecution] | None = None
    """Batch of tools to execute sequentially (requires ``session_id``)."""

    include_page_content: bool | None = None
    """If ``True``, includes raw page content in the response."""


# ── Usage (from Response Headers) ────────────────────────────────


class Usage(BaseModel):
    """Parsed from ``X-Usage-*`` response headers."""

    action_count: int
    """Total actions consumed in the current billing period."""

    action_limit: int
    """Maximum actions allowed in the current billing period."""

    period_start: str
    """Start of the current billing period (ISO 8601)."""


# ── Browse Response ──────────────────────────────────────────────


class BrowseResult(BaseModel):
    """Response from ``POST /v1/browse``."""

    session_id: str
    """Unique identifier for this browser session."""

    url: str
    """The final URL after any redirects."""

    title: str
    """Page title."""

    summary: str
    """AI-generated summary of the page."""

    page_content: str | None = None
    """Raw page content (only when ``include_page_content=True``)."""

    tools: list[Tool]
    """Available tools discovered on this page."""

    results: list[ToolResult] | None = None
    """Results from tool execution, if any tools were invoked."""

    stopped_reason: Literal["navigation", "timeout"] | None = None
    """Why tool execution stopped, if applicable."""

    actions_charged: int | None = None
    """Number of actions metered for this request."""

    usage: Usage | None = None
    """Usage info parsed from response headers.  ``None`` if headers were absent."""


# ── Health ───────────────────────────────────────────────────────


class HealthResult(BaseModel):
    """Response from ``GET /health``."""

    status: Literal["ok", "degraded", "error"]
    uptime_s: float
    active_sessions: int


# ── Usage (from GET /v1/usage) ───────────────────────────────────


class UsageActions(BaseModel):
    """Action consumption for the current billing period."""

    used: int
    """Actions consumed this billing period."""

    limit: int
    """Maximum actions for this plan."""


class UsagePeriod(BaseModel):
    """Billing period boundaries."""

    start: str
    """Period start (ISO 8601)."""

    end: str
    """Period end (ISO 8601)."""


class UsageBilling(BaseModel):
    """Billing & subscription status."""

    has_subscription: bool
    """Whether the tenant has an active paid subscription."""

    portal_url: str | None
    """URL to the billing portal (``None`` if no subscription)."""


class UsageResponse(BaseModel):
    """Response from ``GET /v1/usage``."""

    plan: Literal["free", "builder", "pro"]
    """Active pricing plan."""

    actions: UsageActions
    """Action consumption for the current billing period."""

    period: UsagePeriod
    """Current billing period boundaries."""

    billing: UsageBilling
    """Billing & subscription status."""


# ── Error Code Literal ───────────────────────────────────────────

ErrorCode = Literal[
    "UNAUTHORIZED",
    "INVALID_REQUEST",
    "VALIDATION_ERROR",
    "DOMAIN_BLOCKED",
    "SESSION_NOT_FOUND",
    "SESSION_BUSY",
    "SESSION_EXPIRED",
    "PLAN_RESTRICTED",
    "QUOTA_EXCEEDED",
    "RATE_LIMITED",
    # Concurrent-session limit reached (503 + retry_after).
    "CONCURRENCY_EXCEEDED",
    # Free-tier session admission temporarily unverifiable (503 + retry_after).
    "CONCURRENCY_UNAVAILABLE",
    # Free-tier tool execution degraded to observe-only until UTC midnight (503 + retry_after).
    "FREE_TIER_DEGRADED",
    # Browser infrastructure unavailable (503 + retry_after).
    "BROWSER_ERROR",
    # AI processing failed (502 + retry_after).
    "AI_PROCESSING_ERROR",
    # Bot-challenge/access-denied interstitial (502, no retry_after, unbilled).
    "SITE_BLOCKED",
    "INTERNAL_ERROR",
]
"""All possible machine-readable error codes in API error responses."""
