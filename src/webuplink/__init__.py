"""webuplink — Official Python SDK for WebUplink.

Browse and interact with any public website via named, callable tool definitions.

Usage::

    from webuplink import WebUplink

    client = WebUplink(api_key="wup_your_api_key")
    page = client.browse("https://example.com")
    print(page.tools)

For async usage::

    from webuplink import AsyncWebUplink

    async with AsyncWebUplink() as client:
        page = await client.browse("https://example.com")
"""

from webuplink._client import AsyncWebUplink, WebUplink
from webuplink._errors import (
    APIConnectionError,
    AuthenticationError,
    RateLimitError,
    WebUplinkError,
)
from webuplink._types import (
    BrowseParams,
    BrowseResult,
    ErrorCode,
    HealthResult,
    Tool,
    ToolExecution,
    ToolParam,
    ToolResult,
    Usage,
    UsageResponse,
)
from webuplink._version import __version__

__all__ = [
    # Clients
    "WebUplink",
    "AsyncWebUplink",
    # Errors
    "WebUplinkError",
    "AuthenticationError",
    "RateLimitError",
    "APIConnectionError",
    # Types
    "BrowseParams",
    "BrowseResult",
    "Tool",
    "ToolParam",
    "ToolResult",
    "ToolExecution",
    "Usage",
    "UsageResponse",
    "HealthResult",
    "ErrorCode",
    # Version
    "__version__",
]
