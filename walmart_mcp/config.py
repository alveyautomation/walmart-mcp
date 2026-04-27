"""Configuration for the Walmart Marketplace MCP server.

All settings come from environment variables. Nothing is persisted to disk
and nothing is logged. See `.env.example` for the full list of supported
variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


def _str(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _optional_str(name: str) -> Optional[str]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the MCP server."""

    api_url: str
    consumer_id: str
    private_key_pem: str
    channel_type: Optional[str]
    default_seller_id: Optional[str]
    http_timeout: int
    max_retries: int

    @classmethod
    def from_env(cls) -> "Settings":
        api_url = _str("WALMART_API_URL", "https://marketplace.walmartapis.com/")
        consumer_id = _str("WALMART_CONSUMER_ID")
        private_key_raw = os.environ.get("WALMART_PRIVATE_KEY")
        if private_key_raw is not None:
            # Allow `\n` literal escapes in env vars so multi-line PEM bodies
            # survive process-manager templating without losing newlines.
            private_key_pem = private_key_raw.replace("\\n", "\n").strip()
        else:
            private_key_pem = ""

        missing = [
            name
            for name, value in [
                ("WALMART_API_URL", api_url),
                ("WALMART_CONSUMER_ID", consumer_id),
                ("WALMART_PRIVATE_KEY", private_key_pem or None),
            ]
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
                + ". See .env.example for the full list."
            )

        # Trailing slash is required for path joining
        assert api_url is not None
        if not api_url.endswith("/"):
            api_url = api_url + "/"

        return cls(
            api_url=api_url,
            consumer_id=consumer_id,  # type: ignore[arg-type]
            private_key_pem=private_key_pem,
            channel_type=_optional_str("WALMART_CHANNEL_TYPE"),
            default_seller_id=_optional_str("WALMART_DEFAULT_SELLER_ID"),
            http_timeout=_int("WALMART_HTTP_TIMEOUT", 60),
            max_retries=_int("WALMART_MAX_RETRIES", 3),
        )
