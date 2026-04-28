"""Tests for the Walmart Marketplace HTTP client.

All tests use a mocked `requests.Session`, no live HTTP, no real
credentials. Synthetic fixtures defined in tests/fixtures.py.
"""

from __future__ import annotations

import base64
from datetime import date
from unittest.mock import MagicMock

import pytest
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from walmart_mcp.client import (
    WalmartClient,
    WalmartError,
    _format_date,
    _sign,
)
from tests.fixtures import (
    SAMPLE_INVENTORY,
    SAMPLE_ORDER_DETAIL,
    SAMPLE_ORDER_LIST_PAGE_1,
    SAMPLE_ORDER_LIST_PAGE_2,
    SAMPLE_PRICING,
    SAMPLE_PRODUCT,
    SAMPLE_PRODUCT_LIST,
    SAMPLE_SETTLEMENT_REPORT,
    SANDBOX_CONSUMER_ID,
)


def _ok_response(json_body: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 400
    resp.json.return_value = json_body
    return resp


def _err_response(status: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = False
    resp.json.return_value = {}
    return resp


def _make_client(session: MagicMock, pem: str) -> WalmartClient:
    return WalmartClient(
        base_url="https://sandbox.walmartapis.example/",
        consumer_id=SANDBOX_CONSUMER_ID,
        private_key_pem=pem,
        timeout=5,
        max_retries=3,
        session=session,
    )


# ---- auth / signing ----------------------------------------------------


def test_signature_is_base64_and_verifies(test_private_key_pem):
    pk = serialization.load_pem_private_key(
        test_private_key_pem.encode("utf-8"), password=None
    )
    url = "https://sandbox.walmartapis.example/v3/items/ABC"
    timestamp = "1700000000000"
    sig_b64 = _sign(SANDBOX_CONSUMER_ID, url, "GET", timestamp, pk)

    # Valid base64
    sig_bytes = base64.b64decode(sig_b64)

    # Verify with the matching public key, should not raise
    string_to_sign = f"{SANDBOX_CONSUMER_ID}\n{url}\nGET\n{timestamp}\n"
    pk.public_key().verify(
        sig_bytes,
        string_to_sign.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_request_attaches_walmart_headers(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRODUCT)
    client = _make_client(session, test_private_key_pem)
    client.get_product("ACME-WIDGET-001")

    args, kwargs = session.request.call_args
    headers = kwargs["headers"]
    assert headers["WM_SVC.NAME"] == "Walmart Marketplace"
    assert headers["WM_CONSUMER.ID"] == SANDBOX_CONSUMER_ID
    assert headers["WM_SEC.AUTH_SIGNATURE"]
    assert headers["WM_SEC.TIMESTAMP"]
    assert headers["WM_QOS.CORRELATION_ID"]
    assert headers["Accept"] == "application/json"


def test_channel_type_is_attached_when_configured(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRODUCT)
    client = WalmartClient(
        base_url="https://sandbox.walmartapis.example/",
        consumer_id=SANDBOX_CONSUMER_ID,
        private_key_pem=test_private_key_pem,
        channel_type="abc-channel-guid",
        session=session,
    )
    client.get_product("X")
    headers = session.request.call_args.kwargs["headers"]
    assert headers["WM_CONSUMER.CHANNEL.TYPE"] == "abc-channel-guid"


def test_channel_type_omitted_by_default(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRODUCT)
    client = _make_client(session, test_private_key_pem)
    client.get_product("X")
    headers = session.request.call_args.kwargs["headers"]
    assert "WM_CONSUMER.CHANNEL.TYPE" not in headers


def test_invalid_private_key_raises():
    with pytest.raises(WalmartError, match="Failed to parse"):
        WalmartClient(
            base_url="https://x/",
            consumer_id="c",
            private_key_pem="not a pem",
        )


# ---- error / retry handling -------------------------------------------


def test_500_response_retries_then_raises(test_private_key_pem, monkeypatch):
    import walmart_mcp.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)

    session = MagicMock()
    session.request.return_value = _err_response(500)
    client = _make_client(session, test_private_key_pem)
    with pytest.raises(WalmartError, match="Transient Walmart error"):
        client.get_product("X")
    assert session.request.call_count == 3  # max_retries


def test_520_is_treated_as_transient(test_private_key_pem, monkeypatch):
    import walmart_mcp.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)

    session = MagicMock()
    session.request.return_value = _err_response(520)
    client = _make_client(session, test_private_key_pem)
    with pytest.raises(WalmartError):
        client.get_product("X")
    assert session.request.call_count == 3


def test_connection_error_retries(monkeypatch, test_private_key_pem):
    import walmart_mcp.client as client_module

    monkeypatch.setattr(client_module.time, "sleep", lambda *_: None)

    session = MagicMock()
    session.request.side_effect = [
        requests.ConnectionError("boom"),
        _ok_response(SAMPLE_PRODUCT),
    ]
    client = _make_client(session, test_private_key_pem)
    result = client.get_product("ACME-WIDGET-001")
    assert result["sku"] == "ACME-WIDGET-001"


def test_404_does_not_retry_get_product(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _err_response(404)
    client = _make_client(session, test_private_key_pem)
    # get_product swallows 404 to None
    assert client.get_product("MISSING") is None
    assert session.request.call_count == 1


def test_400_raises_immediately(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _err_response(400)
    client = _make_client(session, test_private_key_pem)
    with pytest.raises(WalmartError) as exc_info:
        client.search_products("widget")
    assert exc_info.value.status_code == 400
    assert session.request.call_count == 1


def test_non_json_body_raises(test_private_key_pem):
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.ok = True
    resp.json.side_effect = ValueError("no json")
    session.request.return_value = resp
    client = _make_client(session, test_private_key_pem)
    with pytest.raises(WalmartError, match="non-JSON body"):
        client.get_product("X")


# ---- read endpoints ----------------------------------------------------


def test_search_products_passes_expected_params(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRODUCT_LIST)
    client = _make_client(session, test_private_key_pem)

    client.search_products(query="widget", page=2, page_size=25)

    args, kwargs = session.request.call_args
    assert args[0] == "GET"
    assert args[1].endswith("/v3/items/walmart/search")
    params = kwargs["params"]
    assert params["query"] == "widget"
    assert params["limit"] == 25
    assert params["offset"] == 25  # (page-1) * page_size


def test_get_product_returns_record(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRODUCT)
    client = _make_client(session, test_private_key_pem)
    result = client.get_product(sku="ACME-WIDGET-001")
    assert result is not None
    assert result["sku"] == "ACME-WIDGET-001"


def test_get_product_url_encodes_sku(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRODUCT)
    client = _make_client(session, test_private_key_pem)
    client.get_product(sku="A B/C")
    url = session.request.call_args.args[1]
    assert "A%20B%2FC" in url


def test_get_product_returns_none_on_404(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _err_response(404)
    client = _make_client(session, test_private_key_pem)
    assert client.get_product(sku="DOES-NOT-EXIST") is None


def test_search_orders_handles_pagination(test_private_key_pem):
    session = MagicMock()
    session.request.side_effect = [
        _ok_response(SAMPLE_ORDER_LIST_PAGE_1),
        _ok_response(SAMPLE_ORDER_LIST_PAGE_2),
    ]
    client = _make_client(session, test_private_key_pem)

    out = list(
        client.search_orders(
            date_from=date(2026, 4, 26),
            date_to=date(2026, 4, 26),
        )
    )
    assert len(out) == 3
    assert {o["purchaseOrderId"] for o in out} == {
        "1234567890001",
        "1234567890002",
        "1234567890003",
    }


def test_search_orders_passes_status_filter(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_ORDER_LIST_PAGE_2)
    client = _make_client(session, test_private_key_pem)
    list(
        client.search_orders(
            date_from=date(2026, 4, 26),
            date_to=date(2026, 4, 26),
            status="Shipped",
        )
    )
    params = session.request.call_args.kwargs["params"]
    assert params["status"] == "Shipped"
    assert params["createdStartDate"] == "2026-04-26"
    assert params["createdEndDate"] == "2026-04-26"


def test_search_orders_rejects_inverted_range(test_private_key_pem):
    session = MagicMock()
    client = _make_client(session, test_private_key_pem)
    with pytest.raises(ValueError, match="date_from must be <= date_to"):
        list(
            client.search_orders(
                date_from=date(2026, 4, 26),
                date_to=date(2026, 4, 25),
            )
        )


def test_get_order_returns_detail(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_ORDER_DETAIL)
    client = _make_client(session, test_private_key_pem)
    result = client.get_order("1234567890001")
    assert result is not None
    assert result["purchaseOrderId"] == "1234567890001"
    assert len(result["orderLines"]["orderLine"]) == 1


def test_get_order_returns_none_on_404(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _err_response(404)
    client = _make_client(session, test_private_key_pem)
    assert client.get_order("99999999") is None


def test_get_inventory_returns_record(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_INVENTORY)
    client = _make_client(session, test_private_key_pem)
    inv = client.get_inventory(sku="ACME-WIDGET-001")
    assert inv is not None
    assert inv["quantity"]["amount"] == 42
    params = session.request.call_args.kwargs["params"]
    assert params["sku"] == "ACME-WIDGET-001"


def test_get_inventory_returns_none_on_404(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _err_response(404)
    client = _make_client(session, test_private_key_pem)
    assert client.get_inventory(sku="MISSING") is None


def test_get_pricing_returns_record(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRICING)
    client = _make_client(session, test_private_key_pem)
    p = client.get_pricing(sku="ACME-WIDGET-001")
    assert p is not None
    assert p["pricing"][0]["currentPrice"]["amount"] == 29.99


def test_get_pricing_returns_none_on_404(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _err_response(404)
    client = _make_client(session, test_private_key_pem)
    assert client.get_pricing(sku="MISSING") is None


def test_get_settlement_report_returns_record(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_SETTLEMENT_REPORT)
    client = _make_client(session, test_private_key_pem)
    rpt = client.get_settlement_report("SETTLE-9001-202604")
    assert rpt is not None
    assert rpt["reportId"] == "SETTLE-9001-202604"
    url = session.request.call_args.args[1]
    assert "/v3/report/reconreport/" in url


def test_get_settlement_report_returns_none_on_404(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _err_response(404)
    client = _make_client(session, test_private_key_pem)
    assert client.get_settlement_report("MISSING") is None


def test_format_date_for_date():
    assert _format_date(date(2026, 1, 5)) == "2026-01-05"
    assert _format_date(date(2026, 12, 31)) == "2026-12-31"


def test_base_url_normalization(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRODUCT)
    client = WalmartClient(
        base_url="https://sandbox.walmartapis.example",  # no trailing slash
        consumer_id=SANDBOX_CONSUMER_ID,
        private_key_pem=test_private_key_pem,
        session=session,
    )
    client.get_product(sku="X")
    assert client.base_url.endswith("/")


def test_max_retries_clamped_to_minimum_one(test_private_key_pem):
    session = MagicMock()
    session.request.return_value = _ok_response(SAMPLE_PRODUCT)
    client = WalmartClient(
        base_url="https://sandbox.walmartapis.example/",
        consumer_id=SANDBOX_CONSUMER_ID,
        private_key_pem=test_private_key_pem,
        max_retries=0,  # nonsense value
        session=session,
    )
    # Should still execute once
    client.get_product(sku="X")
    assert session.request.call_count == 1
