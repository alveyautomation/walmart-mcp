# Changelog

All notable changes to `walmart-mcp` are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0]. 2026-04-26

Initial public release.

### Added

- MCP server entry point (`walmart_mcp/server.py`) using the official `mcp` Python SDK with `FastMCP`.
- Seven read-only tools:
  - `walmart_search_products`
  - `walmart_get_product`
  - `walmart_search_orders`
  - `walmart_get_order`
  - `walmart_get_inventory`
  - `walmart_get_pricing`
  - `walmart_get_settlement_report`
- HTTP client (`walmart_mcp/client.py`):
  - Walmart's signed-request auth (RSA-SHA256 PKCS#1 v1.5, base64-encoded `WM_SEC.AUTH_SIGNATURE` header).
  - Per-request UUID correlation IDs.
  - Optional `WM_CONSUMER.CHANNEL.TYPE` header.
  - Exponential backoff retry on transient `5xx` / `520` and connection errors.
  - Transparent cursor pagination for `search_orders`.
- Configuration via environment variables (`walmart_mcp/config.py`).
- Pytest suite with mocked HTTP responses (all synthetic fixtures, no live API calls).
- Pre-commit configuration: gitleaks, trufflehog, ruff, ruff-format, tenant-fingerprint scrubber.
- MIT license, security policy, contributing guidance in README.

### Notes

- v0.1 is read-only by design. Write endpoints (acknowledge order, ship order, update inventory, update price) are planned for v0.2.
- Integration tests against a live Walmart Marketplace sandbox are gated by `WALMART_INTEGRATION_TESTS=1` and are not exercised by default.
