#!/usr/bin/env python3
"""Probe the MyCarrier preprod Rating API.

Hits ``https://app-integration-preprod-api.azurewebsites.net/feature/rating``
with the payload shape `delivery_mycarrier` actually builds, so we can
confirm the request is well-formed before we wire it into Odoo.

Usage:
    MYCARRIER_EMAIL=admin@example.com MYCARRIER_LOCATION_ID=12345 \
        python scripts/probe_rating_api.py

Both env vars are optional — when unset we send placeholder values so we
can inspect the schema-validation error from MyCarrier.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

import requests


URL = "https://app-integration-preprod-api.azurewebsites.net/feature/rating"


def build_payload(email, location_id):
    return {
        "specVersion": "1",
        "type": "com.mycarrier.carrier.integrations",
        "source": "odoo",
        "id": str(uuid.uuid4()),
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "direction": "outbound",
        "customerEmail": email,
        "locationId": location_id,
        "data": {
            "shipment": {
                "shipmentType": "LTL",
                "stops": [
                    {
                        "stopNumber": 1,
                        "stopType": "PICKUP",
                        "name": "RWI Calgary",
                        "addressLine1": "123 Main St",
                        "city": "Calgary",
                        "stateProvince": "AB",
                        "postalCode": "T2P2M5",
                        "country": {"alpha2Code": "CA"},
                    },
                    {
                        "stopNumber": 2,
                        "stopType": "DELIVERY",
                        "name": "Atlanta Customer",
                        "addressLine1": "456 Peachtree St",
                        "city": "Atlanta",
                        "stateProvince": "GA",
                        "postalCode": "30303",
                        "country": {"alpha2Code": "US"},
                    },
                ],
                "shipmentLineItems": [
                    {
                        "lineItemId": "1",
                        "name": "Steel Brackets",
                        "class": "70",
                        "nmfcItemCode": "",
                        "quantity": 1,
                        "dimensions": {
                            "length": 48,
                            "lengthUOM": "INCHES",
                            "width": 40,
                            "widthUOM": "INCHES",
                            "height": 48,
                            "heightUOM": "INCHES",
                            "weight": 500,
                            "weightUOM": "LB",
                            "quantity": 1,
                            "packageType": "PLTS",
                        },
                    }
                ],
            }
        },
    }


def main():
    email = os.environ.get("MYCARRIER_EMAIL", "")
    location_id = os.environ.get("MYCARRIER_LOCATION_ID", "")
    payload = build_payload(email, location_id)
    print(f"POST {URL}")
    print(f"  customerEmail={email!r}  locationId={location_id!r}")
    response = requests.post(
        URL,
        json=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=120,
    )
    print(f"HTTP {response.status_code}")
    print("--- headers ---")
    for k in ("Content-Type", "Content-Length", "Date", "Server"):
        if k in response.headers:
            print(f"  {k}: {response.headers[k]}")
    print("--- body ---")
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text[:2000])
    return 0 if response.status_code < 500 else 1


if __name__ == "__main__":
    sys.exit(main())
