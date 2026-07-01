# Changelog

## 0.1.0 (2026-06-30)

Initial public release.

### Features

- `browse()` — browse pages and execute tools with string shorthand, `BrowseParams`, or keyword arguments
- `close_session()` — explicit session cleanup
- `health()` — API health check with optional deep component checks
- `get_usage()` — usage and billing information for the authenticated tenant
- Sync (`WebUplink`) and async (`AsyncWebUplink`) clients with context manager support
- Idempotency-aware retry with configurable `max_retries`
- Typed error hierarchy: `WebUplinkError`, `AuthenticationError`, `RateLimitError`, `APIConnectionError`
- `Usage` metadata from `X-Usage-*` response headers
- Pydantic v2 models for all request/response types
- `py.typed` marker for PEP 561 type checker support
- Custom `httpx.Client` / `httpx.AsyncClient` injection for proxies, mTLS, and logging
