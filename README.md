# walmart-mcp

> A Model Context Protocol server for Walmart Marketplace. Plug Claude into your catalog, inventory, orders, pricing, and settlement reports â€” read-only, in five minutes.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-1.x-purple.svg)](https://modelcontextprotocol.io)

## Why this exists

Walmart Marketplace's REST API is well-documented but unbranded â€” every team that automates against it ends up writing the same RSA-signing-and-pagination glue from scratch.

If you use Claude (or any MCP-aware AI assistant) to operate ecommerce day-to-day, that gap is the difference between *"summarize today's Walmart orders"* working out of the box and *"summarize today's Walmart orders"* requiring a custom integration.

`walmart-mcp` closes that gap. It's a tiny, well-tested, MIT-licensed MCP server that exposes seven read-only Walmart Marketplace endpoints to any MCP client. Built from years of running ecommerce automation at scale.

## What you can do with it

Wire this server into Claude Code, Claude Desktop, or any MCP host, then ask things like:

- *"Search for any SKU containing `WIDGET` in my Walmart catalog and show inventory levels."*
- *"How many Walmart orders did we ship yesterday? Group by status."*
- *"Pull purchase order 1234567890001 and tell me which line items are still pending."*
- *"For SKU `ACME-001`, what's the current Walmart price and how does it compare to the previous price?"*
- *"Open settlement report `SETTLE-9001-202604` and break out the fees vs. net settlement."*

Claude reads your Walmart account directly. No copy-paste, no spreadsheets, no custom pipelines.

## Tools (v0.1, all read-only)

| Tool                              | What it does                                                |
| --------------------------------- | ----------------------------------------------------------- |
| `walmart_search_products`         | Free-text search across catalog (name + indexed attributes).|
| `walmart_get_product`             | Fetch one product by exact SKU.                             |
| `walmart_search_orders`           | List orders in a date window, optionally filtered by status.|
| `walmart_get_order`               | Fetch one order by purchase order ID, including line items. |
| `walmart_get_inventory`           | Current quantity / unit / fulfillment lag for one SKU.      |
| `walmart_get_pricing`             | Current price + previous price for one SKU.                 |
| `walmart_get_settlement_report`   | Settlement / reconciliation report detail.                  |

Write endpoints (acknowledge order, ship order, update inventory, update price) are intentionally **not** in v0.1. They are planned for v0.2 once read-only ergonomics settle.

## Install

```bash
pip install walmart-mcp
```

> v0.1 ships from this repository. PyPI publication is pending â€” for now, install with `pip install git+https://github.com/alveyautomation/walmart-mcp` or clone and run `pip install -e .` locally.

## Configure credentials

The server reads everything from environment variables. Copy `.env.example` to `.env` and fill in your seller account:

```bash
WALMART_API_URL=https://marketplace.walmartapis.com/
WALMART_CONSUMER_ID=your-consumer-uuid
WALMART_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----
WALMART_CHANNEL_TYPE=                    # optional
WALMART_DEFAULT_SELLER_ID=               # optional, informational
WALMART_HTTP_TIMEOUT=60                  # optional, seconds
WALMART_MAX_RETRIES=3                    # optional
```

Multi-line PEM keys can be passed with literal `\n` escapes â€” the server unescapes them at startup, so you don't need to fight your process manager's quoting rules.

> **Use a read-only Walmart integration profile.** v0.1 only calls `GET` endpoints, but defense in depth means you should hand the server a key tied to a profile that *cannot* modify anything. When v0.2 lands with write tools, opt-in by upgrading the profile â€” never the other way around.

## Wire into Claude Code

Add to `~/.claude/claude_code_config.json` (or your project's MCP config):

```json
{
  "mcpServers": {
    "walmart": {
      "command": "walmart-mcp",
      "env": {
        "WALMART_API_URL": "https://marketplace.walmartapis.com/",
        "WALMART_CONSUMER_ID": "your-consumer-uuid",
        "WALMART_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\\nMIIE...\\n-----END PRIVATE KEY-----"
      }
    }
  }
}
```

Restart Claude Code. The seven `walmart_*` tools will appear in any new session.

## Wire into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows) and add the same `mcpServers` block as above. Restart the desktop app.

## Tool reference

Every tool returns a JSON envelope:

```json
{ "ok": true,  "data": { ... } }
{ "ok": false, "error": "human-readable message" }
```

### `walmart_search_products`

```python
walmart_search_products(
    query: str,                          # required
    page: int = 1,
    page_size: int = 50,                 # capped at 200
)
```

Example response:

```json
{
  "ok": true,
  "data": {
    "items": [
      { "sku": "ACME-WIDGET-001", "productName": "Acme Widget, Standard", "price": {"currency": "USD", "amount": 29.99} }
    ],
    "total": 1,
    "page": 1,
    "page_size": 50
  }
}
```

### `walmart_get_product`

```python
walmart_get_product(sku: str)
```

Returns the catalog record, or `data: null` if the SKU is not in the seller's catalog.

### `walmart_search_orders`

```python
walmart_search_orders(
    date_from: str,                      # ISO date "YYYY-MM-DD"
    date_to: str,                        # ISO date "YYYY-MM-DD"
    status: str | None = None,           # e.g. "Created", "Acknowledged", "Shipped"
    limit: int = 200,                    # max 1000
)
```

Pagination is handled transparently â€” Walmart returns a `nextCursor` token in `list.meta.nextCursor`; the tool follows it until empty or until `limit` is reached. The response includes `limit_reached: true` when there were more orders than `limit` allowed.

### `walmart_get_order`

```python
walmart_get_order(purchase_order_id: str)
```

Returns the full order record (with `orderLines.orderLine[]`), or `data: null` for a 404.

### `walmart_get_inventory`

```python
walmart_get_inventory(sku: str)
```

The returned record includes:

- `quantity.amount` â€” current sellable units
- `quantity.unit` â€” unit of measure (typically `EACH`)
- `fulfillmentLagTime` â€” days between order and ship (per Walmart's offer terms)

### `walmart_get_pricing`

```python
walmart_get_pricing(sku: str)
```

Returns the current price record, with `currentPrice` and `previousPrice` (when set). Useful for spot-checking promotional pricing.

### `walmart_get_settlement_report`

```python
walmart_get_settlement_report(report_id: str)
```

Per-report settlement / reconciliation detail. Useful for reconciling Walmart payouts against your accounting system.

## Local development

```bash
git clone https://github.com/alveyautomation/walmart-mcp
cd walmart-mcp
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Pre-commit hooks (gitleaks, ruff, formatter, tenant-fingerprint scrubber):

```bash
pip install pre-commit
pre-commit install
```

Integration tests against a real Walmart Marketplace sandbox account are gated behind `WALMART_INTEGRATION_TESTS=1`. They are not required for normal contribution.

## Troubleshooting

**`Failed to parse WALMART_PRIVATE_KEY`** â€” the PEM body did not load. Most common cause: newlines were stripped by the shell or process manager. Try templating with literal `\n` escapes (the server unescapes them at startup) or load from a file via your env-var system.

**`Missing required environment variables`** â€” the server tried to start before its `.env` was loaded. Either export the vars in the parent shell, or ensure your MCP host config includes them in the `env` block.

**`HTTP 401` on every call** â€” usually a clock-skew problem. Walmart's signature includes a millisecond timestamp; if your host clock is more than a few minutes off, signatures will be rejected. Check NTP.

**`HTTP 403` on specific endpoints** â€” your integration profile lacks the `read` scope for that resource. Adjust the profile in Walmart Seller Center.

**Pagination feels slow** â€” Walmart caps order page size at 200 and uses cursor-based pagination. For large date windows, expect multiple round-trips.

## Contributing

Issues and pull requests welcome. Please:

- Run `pytest` before opening a PR (`pip install -e ".[dev]"`).
- Run `pre-commit run --all-files`.
- Keep additions to v0.1 scope read-only. Write endpoints land in v0.2.
- Synthetic data only in tests â€” no real SKUs, customer names, or order numbers.

## License

MIT â€” see [LICENSE](LICENSE).

## Disclaimer

`walmart-mcp` is an unofficial, third-party integration. It is **not endorsed by, affiliated with, or supported by Walmart Inc.** "Walmart" and "Walmart Marketplace" are trademarks of Walmart Inc. Use at your own risk; verify behavior against your seller account before depending on it for production decisions.

