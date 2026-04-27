"""Tests for the MCP server tool layer.

We exercise the tool functions directly (their underlying Python callable)
to avoid spinning up a real MCP transport in unit tests. The functions
return JSON-encoded envelopes; we decode and assert on shape.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from walmart_mcp import server as srv
from tests.fixtures import (
    SAMPLE_INVENTORY,
    SAMPLE_ORDER_DETAIL,
    SAMPLE_ORDER_LIST_PAGE_1,
    SAMPLE_ORDER_LIST_PAGE_2,
    SAMPLE_PRICING,
    SAMPLE_PRODUCT,
    SAMPLE_PRODUCT_LIST,
    SAMPLE_SETTLEMENT_REPORT,
)


def _call(tool, **kwargs):
    """Invoke a FastMCP-registered tool's underlying Python function."""
    func = getattr(tool, "fn", None) or tool
    return func(**kwargs)


def _decode(envelope: str) -> dict:
    return json.loads(envelope)


def _install_fake_client(monkeypatch, **methods):
    """Replace the lazy-instantiated client with a MagicMock."""
    fake = MagicMock()
    for name, value in methods.items():
        getattr(fake, name).return_value = value if not callable(value) else None
        if callable(value) and not isinstance(value, MagicMock):
            getattr(fake, name).side_effect = value
    monkeypatch.setattr(srv, "_get_client", lambda: fake)
    return fake


# ---- search_products --------------------------------------------------


def test_search_products_happy(monkeypatch):
    _install_fake_client(monkeypatch, search_products=SAMPLE_PRODUCT_LIST)
    out = _decode(_call(srv.walmart_search_products, query="widget"))
    assert out["ok"] is True
    assert out["data"]["total"] == 2
    assert out["data"]["items"][0]["sku"] == "ACME-WIDGET-001"


def test_search_products_rejects_blank_query(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.walmart_search_products, query="   "))
    assert out["ok"] is False
    assert "query is required" in out["error"]


def test_search_products_clamps_page_size(monkeypatch):
    fake = _install_fake_client(monkeypatch, search_products=SAMPLE_PRODUCT_LIST)
    _call(srv.walmart_search_products, query="x", page_size=9999)
    assert fake.search_products.call_args.kwargs["page_size"] == 200


def test_search_products_handles_empty_response(monkeypatch):
    _install_fake_client(monkeypatch, search_products={})
    out = _decode(_call(srv.walmart_search_products, query="x"))
    assert out["ok"] is True
    assert out["data"]["items"] == []
    assert out["data"]["total"] == 0


# ---- get_product -------------------------------------------------------


def test_get_product_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_product=SAMPLE_PRODUCT)
    out = _decode(_call(srv.walmart_get_product, sku="ACME-WIDGET-001"))
    assert out["ok"] is True
    assert out["data"]["sku"] == "ACME-WIDGET-001"


def test_get_product_missing_returns_null(monkeypatch):
    _install_fake_client(monkeypatch, get_product=None)
    out = _decode(_call(srv.walmart_get_product, sku="MISSING"))
    assert out["ok"] is True
    assert out["data"] is None


def test_get_product_blank_sku(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.walmart_get_product, sku="   "))
    assert out["ok"] is False


# ---- search_orders -----------------------------------------------------


def test_search_orders_happy(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_orders.return_value = iter(
        SAMPLE_ORDER_LIST_PAGE_1["list"]["elements"]["order"]
        + SAMPLE_ORDER_LIST_PAGE_2["list"]["elements"]["order"]
    )
    out = _decode(
        _call(
            srv.walmart_search_orders,
            date_from="2026-04-26",
            date_to="2026-04-26",
        )
    )
    assert out["ok"] is True
    assert out["data"]["count"] == 3
    assert {o["purchaseOrderId"] for o in out["data"]["orders"]} == {
        "1234567890001",
        "1234567890002",
        "1234567890003",
    }


def test_search_orders_rejects_bad_date(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(
        _call(
            srv.walmart_search_orders,
            date_from="not-a-date",
            date_to="2026-04-26",
        )
    )
    assert out["ok"] is False
    assert "ISO date" in out["error"]


def test_search_orders_respects_limit(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_orders.return_value = iter(
        SAMPLE_ORDER_LIST_PAGE_1["list"]["elements"]["order"]
        + SAMPLE_ORDER_LIST_PAGE_2["list"]["elements"]["order"]
    )
    out = _decode(
        _call(
            srv.walmart_search_orders,
            date_from="2026-04-26",
            date_to="2026-04-26",
            limit=2,
        )
    )
    assert out["data"]["count"] == 2
    assert out["data"]["limit_reached"] is True


def test_search_orders_passes_status(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    fake.search_orders.return_value = iter([])
    _call(
        srv.walmart_search_orders,
        date_from="2026-04-26",
        date_to="2026-04-26",
        status="Shipped",
    )
    assert fake.search_orders.call_args.kwargs["status"] == "Shipped"


# ---- get_order ---------------------------------------------------------


def test_get_order_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_order=SAMPLE_ORDER_DETAIL)
    out = _decode(
        _call(srv.walmart_get_order, purchase_order_id="1234567890001")
    )
    assert out["ok"] is True
    assert out["data"]["purchaseOrderId"] == "1234567890001"


def test_get_order_rejects_blank(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.walmart_get_order, purchase_order_id=""))
    assert out["ok"] is False


def test_get_order_returns_null_for_missing(monkeypatch):
    _install_fake_client(monkeypatch, get_order=None)
    out = _decode(
        _call(srv.walmart_get_order, purchase_order_id="99999999")
    )
    assert out["ok"] is True
    assert out["data"] is None


# ---- get_inventory -----------------------------------------------------


def test_get_inventory_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_inventory=SAMPLE_INVENTORY)
    out = _decode(_call(srv.walmart_get_inventory, sku="ACME-WIDGET-001"))
    assert out["ok"] is True
    assert out["data"]["quantity"]["amount"] == 42


def test_get_inventory_missing(monkeypatch):
    _install_fake_client(monkeypatch, get_inventory=None)
    out = _decode(_call(srv.walmart_get_inventory, sku="MISSING-001"))
    assert out["ok"] is True
    assert out["data"] is None


def test_get_inventory_blank_sku(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.walmart_get_inventory, sku=""))
    assert out["ok"] is False


# ---- get_pricing -------------------------------------------------------


def test_get_pricing_happy(monkeypatch):
    _install_fake_client(monkeypatch, get_pricing=SAMPLE_PRICING)
    out = _decode(_call(srv.walmart_get_pricing, sku="ACME-WIDGET-001"))
    assert out["ok"] is True
    assert out["data"]["pricing"][0]["currentPrice"]["amount"] == 29.99


def test_get_pricing_missing(monkeypatch):
    _install_fake_client(monkeypatch, get_pricing=None)
    out = _decode(_call(srv.walmart_get_pricing, sku="MISSING"))
    assert out["ok"] is True
    assert out["data"] is None


def test_get_pricing_blank_sku(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.walmart_get_pricing, sku=""))
    assert out["ok"] is False


# ---- get_settlement_report --------------------------------------------


def test_get_settlement_report_happy(monkeypatch):
    _install_fake_client(
        monkeypatch, get_settlement_report=SAMPLE_SETTLEMENT_REPORT
    )
    out = _decode(
        _call(srv.walmart_get_settlement_report, report_id="SETTLE-9001-202604")
    )
    assert out["ok"] is True
    assert out["data"]["reportId"] == "SETTLE-9001-202604"


def test_get_settlement_report_missing(monkeypatch):
    _install_fake_client(monkeypatch, get_settlement_report=None)
    out = _decode(
        _call(srv.walmart_get_settlement_report, report_id="MISSING")
    )
    assert out["ok"] is True
    assert out["data"] is None


def test_get_settlement_report_blank(monkeypatch):
    _install_fake_client(monkeypatch)
    out = _decode(_call(srv.walmart_get_settlement_report, report_id=""))
    assert out["ok"] is False


# ---- error propagation -------------------------------------------------


def test_walmart_error_surfaces_as_envelope(monkeypatch):
    fake = _install_fake_client(monkeypatch)
    from walmart_mcp.client import WalmartError

    fake.get_product.side_effect = WalmartError("boom", status_code=503)
    out = _decode(_call(srv.walmart_get_product, sku="X"))
    assert out["ok"] is False
    assert "boom" in out["error"]
