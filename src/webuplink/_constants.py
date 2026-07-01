"""SDK-wide constants."""

from webuplink._version import __version__

DEFAULT_BASE_URL = "https://api.webuplink.ai"
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 120.0

USER_AGENT = f"webuplink-python/{__version__}"

ENV_API_KEY = "WEBUPLINK_API_KEY"
