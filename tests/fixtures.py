"""Synthetic fixtures used across the test suite.

All identifiers, names, and SKUs are invented for testing. Any resemblance
to a real Walmart Marketplace seller is coincidental, this file must
never gain real-world identifiers.
"""

from __future__ import annotations

# Sandbox seller IDs for the test fixtures only. Pick deliberately
# unrealistic numbers so it's obvious if they ever leak into a real API
# call by accident.
SANDBOX_SELLER_PRIMARY = "10000001"
SANDBOX_SELLER_SECONDARY = "10000002"

SANDBOX_CONSUMER_ID = "00000000-0000-0000-0000-000000000000"

SAMPLE_PRODUCT = {
    "mart": "WALMART_US",
    "sku": "ACME-WIDGET-001",
    "wpid": "0RWFAKEWPID01",
    "upc": "00012345678901",
    "gtin": "00012345678901",
    "productName": "Acme Lorem Widget, Standard",
    "shelf": "[\"Home\",\"Storage\"]",
    "productType": "Widget",
    "price": {"currency": "USD", "amount": 29.99},
    "publishedStatus": "PUBLISHED",
    "lifecycleStatus": "ACTIVE",
}

SAMPLE_PRODUCT_LIST = {
    "totalItems": 2,
    "ItemResponse": [
        SAMPLE_PRODUCT,
        {
            "mart": "WALMART_US",
            "sku": "ACME-WIDGET-002",
            "wpid": "0RWFAKEWPID02",
            "productName": "Acme Lorem Widget, Deluxe",
            "price": {"currency": "USD", "amount": 49.99},
            "publishedStatus": "PUBLISHED",
            "lifecycleStatus": "ACTIVE",
        },
    ],
}

SAMPLE_INVENTORY = {
    "sku": "ACME-WIDGET-001",
    "quantity": {"unit": "EACH", "amount": 42},
    "fulfillmentLagTime": 1,
}

SAMPLE_PRICING = {
    "sku": "ACME-WIDGET-001",
    "pricing": [
        {
            "currentPrice": {"currency": "USD", "amount": 29.99},
            "previousPrice": {"currency": "USD", "amount": 34.99},
            "currentPriceType": "REGULAR",
        }
    ],
}

SAMPLE_ORDER_LIST_PAGE_1 = {
    "list": {
        "meta": {
            "totalCount": 3,
            "limit": 200,
            "nextCursor": "?createdStartDate=2026-04-26&createdEndDate=2026-04-26&offset=2",
        },
        "elements": {
            "order": [
                {
                    "purchaseOrderId": "1234567890001",
                    "customerOrderId": "C-100001",
                    "orderDate": "2026-04-26T10:00:00.000Z",
                    "orderLines": {
                        "orderLine": [
                            {
                                "lineNumber": "1",
                                "item": {"sku": "ACME-WIDGET-001"},
                                "charges": {
                                    "charge": [
                                        {
                                            "chargeAmount": {
                                                "currency": "USD",
                                                "amount": 29.99,
                                            }
                                        }
                                    ]
                                },
                            }
                        ]
                    },
                },
                {
                    "purchaseOrderId": "1234567890002",
                    "customerOrderId": "C-100002",
                    "orderDate": "2026-04-26T11:00:00.000Z",
                    "orderLines": {"orderLine": []},
                },
            ]
        },
    }
}

SAMPLE_ORDER_LIST_PAGE_2 = {
    "list": {
        "meta": {"totalCount": 3, "limit": 200, "nextCursor": None},
        "elements": {
            "order": [
                {
                    "purchaseOrderId": "1234567890003",
                    "customerOrderId": "C-100003",
                    "orderDate": "2026-04-26T12:00:00.000Z",
                    "orderLines": {"orderLine": []},
                }
            ]
        },
    }
}

SAMPLE_ORDER_DETAIL = {
    "purchaseOrderId": "1234567890001",
    "customerOrderId": "C-100001",
    "orderDate": "2026-04-26T10:00:00.000Z",
    "shippingInfo": {
        "phone": "555-0100",
        "estimatedDeliveryDate": "2026-04-30",
        "estimatedShipDate": "2026-04-27",
        "methodCode": "Standard",
        "postalAddress": {
            "name": "Test Customer",
            "address1": "1 Test Street",
            "city": "Anytown",
            "state": "ZZ",
            "postalCode": "00000",
            "country": "USA",
            "addressType": "RESIDENTIAL",
        },
    },
    "orderLines": {
        "orderLine": [
            {
                "lineNumber": "1",
                "item": {
                    "productName": "Acme Lorem Widget, Standard",
                    "sku": "ACME-WIDGET-001",
                },
                "charges": {
                    "charge": [
                        {
                            "chargeType": "PRODUCT",
                            "chargeAmount": {"currency": "USD", "amount": 29.99},
                        }
                    ]
                },
                "orderLineQuantity": {"unitOfMeasurement": "EACH", "amount": "1"},
                "statusDate": "2026-04-26T10:00:00.000Z",
                "orderLineStatuses": {
                    "orderLineStatus": [
                        {"status": "Created", "statusQuantity": {"amount": "1"}}
                    ]
                },
            }
        ]
    },
}

SAMPLE_SETTLEMENT_REPORT = {
    "reportId": "SETTLE-9001-202604",
    "reportType": "SETTLEMENT",
    "createdDate": "2026-04-26T00:00:00.000Z",
    "totals": {
        "grossSales": {"currency": "USD", "amount": 1000.00},
        "fees": {"currency": "USD", "amount": -150.00},
        "netSettlement": {"currency": "USD", "amount": 850.00},
    },
    "lineItems": [
        {
            "purchaseOrderId": "1234567890001",
            "transactionType": "SALE",
            "amount": {"currency": "USD", "amount": 29.99},
        }
    ],
}


def generate_test_private_key_pem() -> str:
    """Generate a fresh RSA-2048 PEM for testing.

    Test-only key, never use in production. Generated per-call so test
    runs do not depend on a checked-in key file.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("ascii")
