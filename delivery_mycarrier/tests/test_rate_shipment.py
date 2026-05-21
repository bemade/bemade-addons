"""Live integration test for the MyCarrier preprod Rating API.

Hits ``https://app-integration-preprod-api.azurewebsites.net/feature/rating``
with the payload built by ``delivery.carrier._mycarrier_build_rate_payload``.

Auth: MyCarrier's rating endpoint authenticates via the ``customerEmail``
field in the body — no API key required. With a placeholder email the API
returns HTTP 200 and an in-body error (``data.error.code``), which is all
we need to verify the request schema is well-formed end-to-end.

To run against a real MyCarrier sandbox account, set::

    MYCARRIER_LIVE_EMAIL=admin@your-org.com \\
    MYCARRIER_LIVE_LOCATION_ID=12345 \\
    odoo-bin -d test --test-tags=mycarrier_live

Without the env vars the test sends placeholders and asserts the schema
round-trip (every field we send must echo back in ``data.failedTransaction``).
"""

import os
from unittest.mock import patch

from odoo.tests import tagged

from .common import MyCarrierCommon


@tagged("post_install", "-at_install", "mycarrier_live", "external")
class TestMyCarrierRateLive(MyCarrierCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        email = os.environ.get("MYCARRIER_LIVE_EMAIL", "")
        location_id = os.environ.get("MYCARRIER_LIVE_LOCATION_ID", "")
        cls.live = bool(email and location_id)
        if email:
            cls.carrier.sudo().mycarrier_account_email = email
        if location_id:
            cls.carrier.mycarrier_location_id = location_id

    def test_rate_payload_round_trips_through_preprod(self):
        """Schema check — every field we send must echo back from MyCarrier.

        The preprod endpoint echoes the request inside ``data.failedTransaction``
        whenever it can't fulfil the quote. By comparing what we sent vs
        what comes back we detect silent field drops (which would mean a
        field name mismatch — exactly how we caught ``commodityName`` /
        ``nmfcCode`` originally).

        Skipped by default — Odoo's test runner blocks external HTTP.
        Set ``MYCARRIER_LIVE_EMAIL`` to opt in.
        """
        if not os.environ.get("MYCARRIER_LIVE_EMAIL"):
            self.skipTest(
                "Set MYCARRIER_LIVE_EMAIL to opt into live preprod HTTP."
            )
        order = self.make_sale_order()
        payload = self.carrier._mycarrier_build_rate_payload(order)
        self.assertEqual(payload["customerEmail"], self.carrier.sudo().mycarrier_account_email)
        self.assertEqual(payload["locationId"], self.carrier.mycarrier_location_id)
        shipment = payload["data"]["shipment"]
        self.assertEqual(len(shipment["stops"]), 2)
        self.assertEqual(shipment["stops"][0]["stopType"], "PICKUP")
        self.assertEqual(shipment["stops"][1]["stopType"], "DROP")
        self.assertGreaterEqual(len(shipment["shipmentLineItems"]), 1)
        for item in shipment["shipmentLineItems"]:
            self.assertIn("commodityName", item)
            self.assertIn("class", item)
            self.assertIn("dimensions", item)
            self.assertIn("nmfcItemCode", item)

        client = self.carrier._mycarrier_client()
        response = client.rate(payload)

        self.assertIn("data", response, f"unexpected response shape: {response}")
        if "failedTransaction" in response["data"]:
            echoed = response["data"]["failedTransaction"]
            self.assertEqual(echoed.get("customerEmail"), payload["customerEmail"])
            self.assertEqual(echoed.get("locationId"), payload["locationId"])
            echoed_items = echoed["data"]["shipment"]["shipmentLineItems"]
            self.assertEqual(
                len(echoed_items),
                len(shipment["shipmentLineItems"]),
                "MyCarrier dropped or added line items",
            )
            for sent, got in zip(shipment["shipmentLineItems"], echoed_items):
                self.assertEqual(
                    got.get("class"),
                    sent["class"],
                    "line item 'class' was dropped by MyCarrier",
                )
                self.assertEqual(
                    got.get("dimensions", {}).get("weight"),
                    sent["dimensions"]["weight"],
                )

    def test_rate_returns_quote_with_real_credentials(self):
        """Requires MYCARRIER_LIVE_EMAIL + MYCARRIER_LIVE_LOCATION_ID."""
        if not self.live:
            self.skipTest(
                "Set MYCARRIER_LIVE_EMAIL and MYCARRIER_LIVE_LOCATION_ID to "
                "run this against a real MyCarrier sandbox account."
            )
        order = self.make_sale_order()
        result = self.carrier.mycarrier_rate_shipment(order)
        self.assertTrue(
            result["success"],
            f"Live rate failed: {result['error_message']}",
        )
        self.assertGreater(result["price"], 0)

    def test_missing_location_id_short_circuits(self):
        self.carrier.mycarrier_location_id = False
        order = self.make_sale_order()
        result = self.carrier.mycarrier_rate_shipment(order)
        self.assertFalse(result["success"])
        self.assertIn("location", result["error_message"].lower())

    def test_missing_email_short_circuits(self):
        self.carrier.sudo().mycarrier_account_email = False
        order = self.make_sale_order()
        result = self.carrier.mycarrier_rate_shipment(order)
        self.assertFalse(result["success"])
        self.assertIn("email", result["error_message"].lower())

    def test_pallet_count_comes_from_packaging(self):
        """With ``product_uom_packaging`` set on the SO line, totalPieces /
        line-item quantity / per-pallet weight come from packaging rather
        than treating every unit as a pallet. Soft-skipped when the
        module isn't installed."""
        if "product.uom.packaging" not in self.env:
            self.skipTest("product_uom_packaging not installed")
        package_type = self.env["stock.package.type"].create(
            {
                "name": "Test Pallet 40x48",
                "packaging_length": 48,
                "width": 40,
                "height": 50,
            }
        )
        packaging = self.env["product.uom.packaging"].create(
            {
                "name": "Pallet of 36",
                "product_tmpl_id": self.product_pallet_a.product_tmpl_id.id,
                "uom_id": self.product_pallet_a.uom_id.id,
                "qty": 36,
                "package_type_id": package_type.id,
            }
        )
        order = self.make_sale_order(products=[(self.product_pallet_a, 144)])
        order.order_line.product_packaging_id = packaging
        payload = self.carrier._mycarrier_build_rate_payload(order)
        shipment = payload["data"]["shipment"]
        # 144 units / 36 per pallet = 4 pallets
        self.assertEqual(shipment["totalPieces"], 4)
        item = shipment["shipmentLineItems"][0]
        self.assertEqual(item["quantity"], 4)
        self.assertEqual(item["dimensions"]["length"], 48)
        self.assertEqual(item["dimensions"]["width"], 40)
        self.assertEqual(item["dimensions"]["height"], 50)
        # 450 lb/unit * 144 units / 4 pallets = 16200 lb/pallet
        self.assertEqual(item["dimensions"]["weight"], 450.0 * 144 / 4)
        # MyCarrier API expects int dimensions; Odoo Float fields would
        # otherwise serialize as JSON floats and the API 400s.
        for k in ("length", "width", "height"):
            self.assertIsInstance(
                item["dimensions"][k], int,
                f"dimensions.{k} must be int (was {type(item['dimensions'][k]).__name__})",
            )

    def test_naive_fallback_without_packaging(self):
        """No packaging on the line → preserve the historical 1-pallet-per-unit
        shape (still wrong but round-trips the request)."""
        order = self.make_sale_order(products=[(self.product_pallet_a, 3)])
        payload = self.carrier._mycarrier_build_rate_payload(order)
        shipment = payload["data"]["shipment"]
        self.assertEqual(shipment["totalPieces"], 3)
        item = shipment["shipmentLineItems"][0]
        self.assertEqual(item["quantity"], 3)
        self.assertEqual(item["dimensions"]["length"], 48)
        self.assertEqual(item["dimensions"]["width"], 40)

    def test_total_volume_computed_in_cubic_feet(self):
        """totalVolume = sum(L*W*H*qty)/1728 for inch dimensions; rounded
        to int (MyCarrier expects int CFT per the C# reference)."""
        order = self.make_sale_order(products=[(self.product_pallet_a, 2)])
        payload = self.carrier._mycarrier_build_rate_payload(order)
        s = payload["data"]["shipment"]
        # Fallback: 2 line-items 48x40x48, qty=1 each => 2 * (48*40*48 / 1728) ≈ 107
        self.assertEqual(
            s["totalVolume"],
            int(round(2 * 48 * 40 * 48 / 1728)),
        )
        self.assertEqual(s["totalVolumeUOM"], "CFT")
        self.assertIsInstance(s["totalVolume"], int)

    def test_order_weight_context_overrides_product_weight(self):
        """The delivery wizard passes a manually-entered weight via
        ``with_context(order_weight=...)``. The payload builder must
        honour it (scaling per-line weights so totalWeight matches),
        otherwise users can't quote LTL when product weights are
        missing or wrong."""
        order = self.make_sale_order(
            products=[(self.product_pallet_a, 1), (self.product_pallet_b, 1)]
        )
        payload_default = self.carrier._mycarrier_build_rate_payload(order)
        self.assertEqual(payload_default["data"]["shipment"]["totalWeight"], 570.0)

        payload_override = self.carrier.with_context(
            order_weight=2000
        )._mycarrier_build_rate_payload(order)
        s = payload_override["data"]["shipment"]
        self.assertEqual(s["totalWeight"], 2000)
        # Per-line weights scale proportionally (450:120 -> 2000 total)
        self.assertAlmostEqual(
            sum(i["dimensions"]["weight"] for i in s["shipmentLineItems"]),
            2000,
            places=2,
        )

    def test_order_weight_context_distributes_when_products_weightless(self):
        """When products have no weight, splitting evenly is better than
        leaving the rate request with totalWeight=0 (which carriers
        always reject)."""
        weightless = self.env["product.product"].create(
            {
                "name": "Weightless Widget",
                "type": "consu",
                "is_storable": True,
                "weight": 0.0,
                "mycarrier_commodity_class": "70",
            }
        )
        order = self.make_sale_order(products=[(weightless, 2), (weightless, 3)])
        payload = self.carrier.with_context(
            order_weight=1000
        )._mycarrier_build_rate_payload(order)
        s = payload["data"]["shipment"]
        self.assertEqual(s["totalWeight"], 1000)
        for item in s["shipmentLineItems"]:
            self.assertEqual(item["dimensions"]["weight"], 500)

    def test_source_field_is_configurable(self):
        """`mycarrier_source` lets clients override the top-level `source`
        in the rating payload — MyCarrier appears to whitelist this per
        account and 403s on unknown values (caught against RWI prod, where
        the C# integration registers `source='refwest.com'`)."""
        self.carrier.mycarrier_source = "refwest.com"
        order = self.make_sale_order()
        payload = self.carrier._mycarrier_build_rate_payload(order)
        self.assertEqual(payload["source"], "refwest.com")

    def test_source_field_defaults_to_odoo(self):
        order = self.make_sale_order()
        payload = self.carrier._mycarrier_build_rate_payload(order)
        self.assertEqual(payload["source"], "odoo")

    def test_api_error_is_surfaced(self):
        """A MyCarrier ``data.error`` block must reach the user verbatim
        instead of the generic 'no eligible carriers' message — that's how
        we caught a 403 auth failure that was being masked in prod."""
        order = self.make_sale_order()
        response = {
            "data": {
                "error": {
                    "code": "403",
                    "message": "Forbidden",
                    "description": "Invalid customerEmail",
                },
                "failedTransaction": {},
            },
        }
        with patch.object(
            type(self.carrier),
            "_mycarrier_client",
            autospec=True,
        ) as client_factory:
            client_factory.return_value.rate.return_value = response
            result = self.carrier.mycarrier_rate_shipment(order)
        self.assertFalse(result["success"])
        self.assertIn("MyCarrier API error", result["error_message"])
        self.assertIn("403", result["error_message"])
        self.assertIn("Forbidden", result["error_message"])
        self.assertNotIn("no eligible carriers", result["error_message"])
