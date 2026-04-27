"""Tests for walmart_mcp.config.Settings."""

from __future__ import annotations

import pytest

from walmart_mcp.config import Settings
from tests.fixtures import SANDBOX_CONSUMER_ID


def test_settings_from_env_happy_path(monkeypatch, test_private_key_pem):
    monkeypatch.setenv("WALMART_API_URL", "https://sandbox.walmartapis.example/")
    monkeypatch.setenv("WALMART_CONSUMER_ID", SANDBOX_CONSUMER_ID)
    monkeypatch.setenv("WALMART_PRIVATE_KEY", test_private_key_pem)
    monkeypatch.setenv("WALMART_CHANNEL_TYPE", "00000000-1111-2222-3333-444444444444")
    monkeypatch.setenv("WALMART_DEFAULT_SELLER_ID", "10000001")
    monkeypatch.setenv("WALMART_HTTP_TIMEOUT", "45")
    monkeypatch.setenv("WALMART_MAX_RETRIES", "5")

    s = Settings.from_env()
    assert s.api_url == "https://sandbox.walmartapis.example/"
    assert s.consumer_id == SANDBOX_CONSUMER_ID
    assert "BEGIN PRIVATE KEY" in s.private_key_pem
    assert s.channel_type == "00000000-1111-2222-3333-444444444444"
    assert s.default_seller_id == "10000001"
    assert s.http_timeout == 45
    assert s.max_retries == 5


def test_settings_default_api_url_when_unset(monkeypatch, test_private_key_pem):
    monkeypatch.delenv("WALMART_API_URL", raising=False)
    monkeypatch.setenv("WALMART_CONSUMER_ID", SANDBOX_CONSUMER_ID)
    monkeypatch.setenv("WALMART_PRIVATE_KEY", test_private_key_pem)

    s = Settings.from_env()
    assert s.api_url == "https://marketplace.walmartapis.com/"


def test_settings_appends_trailing_slash(monkeypatch, test_private_key_pem):
    monkeypatch.setenv("WALMART_API_URL", "https://sandbox.walmartapis.example")
    monkeypatch.setenv("WALMART_CONSUMER_ID", SANDBOX_CONSUMER_ID)
    monkeypatch.setenv("WALMART_PRIVATE_KEY", test_private_key_pem)

    s = Settings.from_env()
    assert s.api_url.endswith("/")


def test_settings_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("WALMART_CONSUMER_ID", raising=False)
    monkeypatch.delenv("WALMART_PRIVATE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        Settings.from_env()


def test_settings_optional_fields_blank(monkeypatch, test_private_key_pem):
    monkeypatch.setenv("WALMART_API_URL", "https://sandbox.walmartapis.example/")
    monkeypatch.setenv("WALMART_CONSUMER_ID", SANDBOX_CONSUMER_ID)
    monkeypatch.setenv("WALMART_PRIVATE_KEY", test_private_key_pem)
    monkeypatch.setenv("WALMART_CHANNEL_TYPE", "")
    monkeypatch.setenv("WALMART_DEFAULT_SELLER_ID", "")

    s = Settings.from_env()
    assert s.channel_type is None
    assert s.default_seller_id is None


def test_settings_invalid_int(monkeypatch, test_private_key_pem):
    monkeypatch.setenv("WALMART_API_URL", "https://sandbox.walmartapis.example/")
    monkeypatch.setenv("WALMART_CONSUMER_ID", SANDBOX_CONSUMER_ID)
    monkeypatch.setenv("WALMART_PRIVATE_KEY", test_private_key_pem)
    monkeypatch.setenv("WALMART_HTTP_TIMEOUT", "not-a-number")

    with pytest.raises(ValueError, match="must be an integer"):
        Settings.from_env()


def test_settings_default_timeout_and_retries(monkeypatch, test_private_key_pem):
    monkeypatch.setenv("WALMART_API_URL", "https://sandbox.walmartapis.example/")
    monkeypatch.setenv("WALMART_CONSUMER_ID", SANDBOX_CONSUMER_ID)
    monkeypatch.setenv("WALMART_PRIVATE_KEY", test_private_key_pem)
    monkeypatch.delenv("WALMART_HTTP_TIMEOUT", raising=False)
    monkeypatch.delenv("WALMART_MAX_RETRIES", raising=False)

    s = Settings.from_env()
    assert s.http_timeout == 60
    assert s.max_retries == 3


def test_settings_unescapes_newlines_in_private_key(monkeypatch):
    """Process managers often template multi-line PEMs as `\\n`-escaped strings."""
    pem_one_line = (
        "-----BEGIN PRIVATE KEY-----\\nfakebase64==\\n-----END PRIVATE KEY-----"
    )
    monkeypatch.setenv("WALMART_API_URL", "https://sandbox.walmartapis.example/")
    monkeypatch.setenv("WALMART_CONSUMER_ID", SANDBOX_CONSUMER_ID)
    monkeypatch.setenv("WALMART_PRIVATE_KEY", pem_one_line)

    s = Settings.from_env()
    assert "\n" in s.private_key_pem
    assert "\\n" not in s.private_key_pem
