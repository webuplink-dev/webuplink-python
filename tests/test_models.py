"""
Unit tests for Pydantic models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from webuplink import BrowseParams, BrowseResult, Tool, ToolExecution, ToolParam, ToolResult, Usage


def test_tool_param() -> None:
    p = ToolParam(name="query", description="Search query")
    assert p.name == "query"


def test_tool() -> None:
    t = Tool(name="search", description="Search", params=[ToolParam(name="q", description="Query")])
    assert len(t.params) == 1


def test_tool_result_success() -> None:
    r = ToolResult(tool="search", success=True)
    assert r.error is None


def test_tool_result_failure() -> None:
    r = ToolResult(tool="search", success=False, error="Not found")
    assert r.error == "Not found"


def test_tool_execution() -> None:
    e = ToolExecution(tool="click", params={"target": "btn"})
    assert e.tool == "click"
    assert e.params == {"target": "btn"}


def test_tool_execution_requires_fields() -> None:
    with pytest.raises(ValidationError):
        ToolExecution()  # type: ignore[call-arg]


def test_browse_params_excludes_none() -> None:
    p = BrowseParams(url="https://example.com")
    dumped = p.model_dump(exclude_none=True)
    assert dumped == {"url": "https://example.com"}
    assert "session_id" not in dumped


def test_browse_result_round_trip() -> None:
    data = {
        "session_id": "s1",
        "url": "https://example.com",
        "title": "Example",
        "summary": "A page",
        "tools": [{"name": "click", "description": "Click", "params": []}],
    }
    result = BrowseResult(**data)
    assert result.session_id == "s1"
    assert result.page_content is None
    assert result.usage is None

    # Round-trip
    dumped = result.model_dump()
    restored = BrowseResult(**dumped)
    assert restored.session_id == "s1"


def test_browse_result_with_usage() -> None:
    data = {
        "session_id": "s1",
        "url": "u",
        "title": "t",
        "summary": "s",
        "tools": [],
        "usage": {"action_count": 5, "action_limit": 100, "period_start": "2026-06-01"},
    }
    result = BrowseResult(**data)
    assert result.usage is not None
    assert result.usage.action_count == 5


def test_browse_result_invalid() -> None:
    with pytest.raises(ValidationError):
        BrowseResult(session_id="s1")  # type: ignore[call-arg]  # missing required fields


def test_usage() -> None:
    u = Usage(action_count=10, action_limit=100, period_start="2026-06-01T00:00:00Z")
    assert u.action_count == 10


def test_error_code_union_matches_server_taxonomy() -> None:
    """Pin the ErrorCode literal to the codes the API actually emits."""
    from typing import get_args

    from webuplink import ErrorCode

    codes = set(get_args(ErrorCode))
    assert codes == {
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
        "CONCURRENCY_EXCEEDED",
        "CONCURRENCY_UNAVAILABLE",
        "FREE_TIER_DEGRADED",
        "BROWSER_ERROR",
        "AI_PROCESSING_ERROR",
        "SITE_BLOCKED",
        "INTERNAL_ERROR",
    }
    # PAGE_ANALYSIS_FAILED was removed — never emitted by the API.
    assert "PAGE_ANALYSIS_FAILED" not in codes
