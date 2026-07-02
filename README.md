<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset=".github/logo-light.svg">
  <img alt="WebUplink" src=".github/logo-light.svg" width="200">
</picture>

### The whole web, as function calls.

[![PyPI version](https://img.shields.io/pypi/v/webuplink.svg)](https://pypi.org/project/webuplink/)
[![CI](https://github.com/webuplink-dev/webuplink-python/actions/workflows/ci.yml/badge.svg)](https://github.com/webuplink-dev/webuplink-python/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Official Python SDK for [WebUplink](https://webuplink.ai).

## Installation

```bash
pip install webuplink
```

## Quickstart

```python
from webuplink import WebUplink

client = WebUplink()  # reads WEBUPLINK_API_KEY from env

# Browse a page — get back structured, callable tools
page = client.browse("https://example.com")
print(page.summary)
print(page.tools)  # [Tool(name='...', description='...', params=[...]), ...]

# Execute a tool discovered on the page
tool = page.tools[0]
result = client.browse(
    session_id=page.session_id,
    tool=tool.name,
    params={tool.params[0].name: "some value"},
)

# Clean up
client.close_session(page.session_id)
```

## Async

```python
from webuplink import AsyncWebUplink

async with AsyncWebUplink() as client:
    page = await client.browse("https://example.com")
    print(page.tools)
```

## What you can build

- **AI agents that act on the web** — browse any site, get back named, callable tool definitions, execute actions
- **No selectors, no scraping** — WebUplink understands pages and generates callable tools automatically
- **Multi-step workflows** — sessions persist across navigations, so your agent can search → filter → select → checkout
- **Any website, zero configuration** — works on sites you've never seen before

## Error handling

Every non-2xx response raises a typed `WebUplinkError` carrying the machine-readable `code`, HTTP `status_code`, and `request_id` (cite it in support tickets):

```python
from webuplink import WebUplink, WebUplinkError

client = WebUplink()

try:
    page = client.browse("https://example.com")
except WebUplinkError as err:
    print(err.code)         # e.g. 'QUOTA_EXCEEDED', 'SITE_BLOCKED'
    print(err.status_code)  # e.g. 429, 502
    print(err.request_id)   # 'req-abc-123'
```

Transient errors that carry `retry_after` (e.g. `BROWSER_ERROR`, `AI_PROCESSING_ERROR`) are retried automatically for observe-only requests. `SITE_BLOCKED` — the site served a bot-verification challenge or access-denied page; the request is **not billed** — carries no `retry_after` and is never auto-retried. Tool executions are never auto-retried (non-idempotent).

Full error reference at **[webuplink.ai/docs/errors](https://webuplink.ai/docs/errors)**.

## Documentation

Full reference at **[webuplink.ai/docs](https://webuplink.ai/docs)**.

## Contributing

```bash
git clone https://github.com/webuplink-dev/webuplink-python.git
cd webuplink-python
pip install -e ".[dev]"
pytest
```

## License

MIT
