"""HTTP client for the Walmart Marketplace REST API.

The client wraps the public REST surface Walmart Marketplace exposes at
`marketplace.walmartapis.com`. Auth is signed-request based, every call
attaches a fresh `WM_SEC.AUTH_SIGNATURE` header computed from the consumer
ID, request URL, HTTP method, and a millisecond timestamp, signed with the
seller's RSA private key (PKCS#8, SHA-256).

The client is deliberately small and dependency-light: only `requests` and
`cryptography` are required at runtime. State is per-instance, there is no
module-level mutable state, so multiple clients can run in the same process
against different sellers without interfering.

This module is a clean rewrite for public release. It does not import or
inherit any seller-specific configuration; everything that depends on a
particular Walmart Marketplace account is supplied by the caller.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date, datetime
from typing import Any, Iterator, Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)

# Walmart's order list endpoint paginates with a `nextCursor` token rather
# than a page number. Items endpoint paginates with `nextCursor` too on v3.
ORDER_PAGE_LIMIT = 200
ITEM_PAGE_LIMIT = 200

# Status codes that warrant a retry. Walmart returns 520 for some upstream
# transient errors as well as the conventional 5xx set.
_RETRY_STATUS_CODES = frozenset({500, 502, 503, 504, 520})

# Walmart's signature scheme is documented at:
# https://developer.walmart.com/api/us/mp/items#auth
# String-to-sign = ConsumerId\nUrl\nMethod\nTimestamp\n
_SVC_NAME = "Walmart Marketplace"


class WalmartError(Exception):
    """Wraps a non-recoverable Walmart Marketplace response so the MCP layer
    can surface a clean message instead of leaking the raw HTTP exception."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _load_private_key(pem: str) -> rsa.RSAPrivateKey:
    """Load a PEM-encoded RSA private key (PKCS#8 or PKCS#1)."""
    try:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception as exc:  # pragma: no cover - cryptography raises various subtypes
        raise WalmartError(f"Failed to parse WALMART_PRIVATE_KEY: {exc}") from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise WalmartError("WALMART_PRIVATE_KEY must be an RSA private key")
    return key


def _sign(consumer_id: str, url: str, method: str, timestamp_ms: str,
          private_key: rsa.RSAPrivateKey) -> str:
    """Produce the base64-encoded RSA-SHA256 signature for a Walmart request."""
    import base64

    string_to_sign = f"{consumer_id}\n{url}\n{method.upper()}\n{timestamp_ms}\n"
    signature = private_key.sign(
        string_to_sign.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


class WalmartClient:
    """Thin REST wrapper. Construct once per (seller, credential) pair."""

    def __init__(
        self,
        base_url: str,
        consumer_id: str,
        private_key_pem: str,
        *,
        channel_type: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
    ):
        if not base_url.endswith("/"):
            base_url = base_url + "/"
        self.base_url = base_url
        self._consumer_id = consumer_id
        self._private_key = _load_private_key(private_key_pem)
        self._channel_type = channel_type
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._session = session or requests.Session()

    # ---- auth -----------------------------------------------------------

    def _headers(self, url: str, method: str) -> dict:
        timestamp_ms = str(int(time.time() * 1000))
        signature = _sign(
            self._consumer_id, url, method, timestamp_ms, self._private_key
        )
        headers = {
            "WM_SVC.NAME": _SVC_NAME,
            "WM_QOS.CORRELATION_ID": str(uuid.uuid4()),
            "WM_SEC.TIMESTAMP": timestamp_ms,
            "WM_SEC.AUTH_SIGNATURE": signature,
            "WM_CONSUMER.ID": self._consumer_id,
            "Accept": "application/json",
        }
        if self._channel_type:
            headers["WM_CONSUMER.CHANNEL.TYPE"] = self._channel_type
        return headers

    # ---- request loop --------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        *,
        json_body: Optional[dict] = None,
    ) -> Any:
        url = f"{self.base_url}{path.lstrip('/')}"
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._session.request(
                    method,
                    url,
                    headers=self._headers(url, method),
                    params=params,
                    json=json_body,
                    timeout=self._timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if resp.status_code in _RETRY_STATUS_CODES:
                last_exc = WalmartError(
                    f"Transient Walmart error: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )
                self._sleep_backoff(attempt)
                continue

            if not resp.ok:
                raise WalmartError(
                    f"Walmart {method} {path} failed: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )

            try:
                return resp.json()
            except ValueError as exc:
                raise WalmartError(
                    f"Walmart {method} {path} returned non-JSON body"
                ) from exc

        if last_exc is not None:
            raise WalmartError(
                f"Walmart {method} {path} failed after "
                f"{self._max_retries} attempts: {last_exc}"
            ) from last_exc
        raise WalmartError(
            f"Walmart {method} {path} failed for unknown reason"
        )

    @staticmethod
    def _sleep_backoff(attempt: int) -> None:
        # Exponential backoff with a small floor: 0.5s, 1s, 2s, 4s ...
        delay = 0.5 * (2 ** (attempt - 1))
        time.sleep(min(delay, 8.0))

    # ---- public read endpoints -----------------------------------------

    def search_products(
        self,
        query: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Search the seller's catalog by free-text query.

        Walmart's items endpoint accepts a `sku` filter for exact match and
        a `nextCursor` for pagination. For free-text we lean on the search
        path; results come back wrapped in `ItemResponse`.
        """
        params: dict[str, Any] = {
            "query": query,
            "limit": max(1, min(page_size, ITEM_PAGE_LIMIT)),
            "offset": max(0, (page - 1) * page_size),
        }
        return self._request("GET", "v3/items/walmart/search", params=params)

    def get_product(self, sku: str) -> Optional[dict]:
        """Return the catalog record for an exact SKU, or None if absent."""
        try:
            return self._request("GET", f"v3/items/{_quote(sku)}")
        except WalmartError as exc:
            if exc.status_code == 404:
                return None
            raise

    def search_orders(
        self,
        date_from: date,
        date_to: date,
        *,
        status: Optional[str] = None,
    ) -> Iterator[dict]:
        """Yield every order created in the inclusive [date_from, date_to] range.

        Walmart paginates orders with a `nextCursor` query string returned
        in `meta.nextCursor`. Iteration stops when the cursor is absent.
        """
        if date_from > date_to:
            raise ValueError("date_from must be <= date_to")

        params: dict[str, Any] = {
            "createdStartDate": _format_date(date_from),
            "createdEndDate": _format_date(date_to),
            "limit": ORDER_PAGE_LIMIT,
        }
        if status:
            params["status"] = status

        path = "v3/orders"
        while True:
            data = self._request("GET", path, params=params)
            elements = (data.get("list") or {}).get("elements") or {}
            orders = elements.get("order") or []
            for order in orders:
                yield order

            meta = data.get("list", {}).get("meta") or {}
            next_cursor = meta.get("nextCursor")
            if not next_cursor or not orders:
                return
            # Walmart returns nextCursor as a leading-`?` query string. Strip
            # it and merge into params for the next call.
            cursor = next_cursor.lstrip("?")
            params = dict(p.split("=", 1) for p in cursor.split("&") if "=" in p)

    def get_order(self, purchase_order_id: str) -> Optional[dict]:
        """Return full order detail (including line items), or None if missing."""
        try:
            return self._request("GET", f"v3/orders/{_quote(purchase_order_id)}")
        except WalmartError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_inventory(self, sku: str) -> Optional[dict]:
        """Return the current inventory record for `sku`."""
        try:
            return self._request(
                "GET",
                "v3/inventory",
                params={"sku": sku},
            )
        except WalmartError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_pricing(self, sku: str) -> Optional[dict]:
        """Return the current pricing rules for `sku`."""
        try:
            return self._request(
                "GET",
                "v3/price",
                params={"sku": sku},
            )
        except WalmartError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_settlement_report(self, report_id: str) -> Optional[dict]:
        """Return the detail for a settlement / reconciliation report."""
        try:
            return self._request(
                "GET",
                f"v3/report/reconreport/{_quote(report_id)}",
            )
        except WalmartError as exc:
            if exc.status_code == 404:
                return None
            raise


def _quote(value: str) -> str:
    """URL-encode a path segment without touching the leading slash."""
    from urllib.parse import quote

    return quote(value, safe="")


def _format_date(d: date) -> str:
    """Format a date as Walmart's createdStartDate expects: ISO 8601 (YYYY-MM-DD)."""
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()
