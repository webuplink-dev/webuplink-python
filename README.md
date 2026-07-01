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

- **AI agents that act on the web** — browse any site, get back typed tool definitions, execute actions
- **No selectors, no scraping** — WebUplink understands pages and generates callable tools automatically
- **Multi-step workflows** — sessions persist across navigations, so your agent can search → filter → select → checkout
- **Any website, zero configuration** — works on sites you've never seen before

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
