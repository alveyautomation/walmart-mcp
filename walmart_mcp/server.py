"""MCP server entry point.

Exposes seven read-only tools that wrap Walmart Marketplace's REST API.
The server uses stdio transport, which is the standard MCP transport for
desktop Claude clients (Claude Code, Claude Desktop, IDE extensions).

Run via `python -m walmart_mcp` or the `walmart-mcp` CLI command.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .client import WalmartClient, WalmartError
from .config import Settings

logger = logging.getLogger(__name__)

mcp = FastMCP("walmart-mcp")

# Lazy singletons. We don't want to require credentials at import time —
# the MCP host may launch the server with a degenerate environment for
# capability discovery.
_settings: Optional[Settings] = None
_client: Optional[WalmartClient] = None


def _get_client() -> WalmartClient:
    global _settings, _client
    if _client is None:
        _settings = Settings.from_env()
        _client = WalmartClient(
            base_url=_settings.api_url,
            consumer_id=_settings.consumer_id,
            private_key_pem=_settings.private_key_pem,
            channel_type=_settings.channel_type,
            timeout=_settings.http_timeout,
            max_retries=_settings.max_retries,
        )
    return _client


def _ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, default=_json_default, indent=2)


def _err(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, indent=2)


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO date (YYYY-MM-DD); got {value!r}"
        ) from exc


# ---- tools -------------------------------------------------------------


@mcp.tool()
def walmart_search_products(query: str, page: int = 1, page_size: int = 50) -> str:
    """Search the Walmart Marketplace catalog by free-text query.

    Args:
        query: Free-text search string. Matches against product name and
            indexed catalog attributes.
        page: 1-indexed page number.
        page_size: Page size (max 200, capped server-side).

    Returns:
        JSON envelope: {"ok": true, "data": {"items": [...], "total": N}}.
    """
    if not query or not query.strip():
        return _err("query is required and must be non-empty")
    try:
        result = _get_client().search_products(
            query=query.strip(),
            page=max(1, page),
            page_size=max(1, min(page_size, 200)),
        )
        # Walmart wraps lists in `ItemResponse`; expose a flat shape.
        items = result.get("ItemResponse") or result.get("items") or []
        total = result.get("totalItems")
        if total is None:
            total = len(items)
        return _ok(
            {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }
        )
    except (ValueError, WalmartError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def walmart_get_product(sku: str) -> str:
    """Fetch the full catalog record for a single SKU.

    Args:
        sku: Exact seller SKU to look up.

    Returns:
        JSON envelope. `data` is the product record, or null when the SKU
        is not present in the seller's catalog.
    """
    if not sku or not sku.strip():
        return _err("sku is required and must be non-empty")
    try:
        product = _get_client().get_product(sku=sku.strip())
        return _ok(product)
    except (ValueError, WalmartError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def walmart_search_orders(
    date_from: str,
    date_to: str,
    status: Optional[str] = None,
    limit: int = 200,
) -> str:
    """Search orders created in the inclusive [date_from, date_to] window.

    Args:
        date_from: ISO date (YYYY-MM-DD), start of window.
        date_to: ISO date (YYYY-MM-DD), end of window.
        status: Optional Walmart order status filter (e.g. "Created",
            "Acknowledged", "Shipped", "Delivered", "Cancelled").
        limit: Cap on yielded orders (default 200, max 1000).

    Returns:
        JSON envelope. `data.orders` is the list of order records.
    """
    try:
        df = _parse_date(date_from, "date_from")
        dt = _parse_date(date_to, "date_to")
        capped_limit = max(1, min(limit, 1000))
        client = _get_client()
        out: list[dict] = []
        for order in client.search_orders(
            date_from=df,
            date_to=dt,
            status=status.strip() if status else None,
        ):
            out.append(order)
            if len(out) >= capped_limit:
                break
        return _ok(
            {
                "orders": out,
                "count": len(out),
                "date_from": df.isoformat(),
                "date_to": dt.isoformat(),
                "status": status,
                "limit_reached": len(out) >= capped_limit,
            }
        )
    except (ValueError, WalmartError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def walmart_get_order(purchase_order_id: str) -> str:
    """Fetch full order detail including line items.

    Args:
        purchase_order_id: Walmart purchase order ID (string, e.g.
            "1234567891234").

    Returns:
        JSON envelope. `data` is the order record, or null if the order
        does not exist.
    """
    if not purchase_order_id or not purchase_order_id.strip():
        return _err("purchase_order_id is required and must be non-empty")
    try:
        order = _get_client().get_order(purchase_order_id=purchase_order_id.strip())
        return _ok(order)
    except (ValueError, WalmartError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def walmart_get_inventory(sku: str) -> str:
    """Fetch the current inventory record for a single SKU.

    Args:
        sku: Exact seller SKU.

    Returns:
        JSON envelope. `data` is the inventory record (with quantity,
        unit, fulfillment lag time), or null if absent.
    """
    if not sku or not sku.strip():
        return _err("sku is required and must be non-empty")
    try:
        inv = _get_client().get_inventory(sku=sku.strip())
        return _ok(inv)
    except (ValueError, WalmartError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def walmart_get_pricing(sku: str) -> str:
    """Fetch current pricing rules for a single SKU.

    Args:
        sku: Exact seller SKU.

    Returns:
        JSON envelope. `data` is the pricing record (current price,
        previous price, currency), or null if no pricing rule is set.
    """
    if not sku or not sku.strip():
        return _err("sku is required and must be non-empty")
    try:
        pricing = _get_client().get_pricing(sku=sku.strip())
        return _ok(pricing)
    except (ValueError, WalmartError, RuntimeError) as exc:
        return _err(str(exc))


@mcp.tool()
def walmart_get_settlement_report(report_id: str) -> str:
    """Fetch a settlement / reconciliation report by report ID.

    Args:
        report_id: Walmart settlement report identifier.

    Returns:
        JSON envelope. `data` is the report payload, or null if the
        report is not found.
    """
    if not report_id or not report_id.strip():
        return _err("report_id is required and must be non-empty")
    try:
        report = _get_client().get_settlement_report(report_id=report_id.strip())
        return _ok(report)
    except (ValueError, WalmartError, RuntimeError) as exc:
        return _err(str(exc))


def main() -> None:
    """CLI entry point — runs the MCP server over stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    main()
