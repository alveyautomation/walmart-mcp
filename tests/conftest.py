"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
from typing import Iterator
from unittest.mock import MagicMock

import pytest

from tests.fixtures import (
    SANDBOX_CONSUMER_ID,
    generate_test_private_key_pem,
)

# Generate one RSA key for the entire test session to avoid the 2048-bit
# generation cost on every fixture instantiation.
_SESSION_PRIVATE_KEY_PEM = generate_test_private_key_pem()


@pytest.fixture(scope="session")
def test_private_key_pem() -> str:
    return _SESSION_PRIVATE_KEY_PEM


@pytest.fixture(autouse=True)
def _reset_server_singletons():
    """Each test starts with a fresh server-module singleton state.

    The MCP server lazily caches a Settings + WalmartClient instance.
    Reset between tests so env-var changes take effect and one test's
    mock client doesn't leak into the next.
    """
    from walmart_mcp import server as srv

    srv._settings = None
    srv._client = None
    yield
    srv._settings = None
    srv._client = None


@pytest.fixture
def env_credentials(monkeypatch, test_private_key_pem) -> Iterator[None]:
    monkeypatch.setenv("WALMART_API_URL", "https://sandbox.walmartapis.example/")
    monkeypatch.setenv("WALMART_CONSUMER_ID", SANDBOX_CONSUMER_ID)
    monkeypatch.setenv("WALMART_PRIVATE_KEY", test_private_key_pem)
    monkeypatch.setenv("WALMART_DEFAULT_SELLER_ID", "10000001")
    yield


@pytest.fixture
def mock_session() -> MagicMock:
    """A mocked `requests.Session` that returns canned JSON bodies."""
    return MagicMock()


@pytest.fixture
def client(mock_session, test_private_key_pem):
    from walmart_mcp.client import WalmartClient

    return WalmartClient(
        base_url="https://sandbox.walmartapis.example/",
        consumer_id=SANDBOX_CONSUMER_ID,
        private_key_pem=test_private_key_pem,
        timeout=10,
        max_retries=2,
        session=mock_session,
    )


def _integration_enabled() -> bool:
    return os.environ.get("WALMART_INTEGRATION_TESTS") == "1"


integration_only = pytest.mark.skipif(
    not _integration_enabled(),
    reason="Integration tests require WALMART_INTEGRATION_TESTS=1 + valid creds",
)
