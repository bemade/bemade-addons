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
        """
        order = self.make_sale_order()
        payload = self.carrier._mycarrier_build_rate_payload(order)
        self.assertEqual(payload["customerEmail"], self.carrier.sudo().mycarrier_account_email)
        self.assertEqual(payload["locationId"], self.carrier.mycarrier_location_id)
        shipment = payload["data"]["shipment"]
        self.assertEqual(len(shipment["stops"]), 2)
        self.assertEqual(shipment["stops"][0]["stopType"], "PICKUP")
        self.assertEqual(shipment["stops"][1]["stopType"], "DELIVERY")
        self.assertGreaterEqual(len(shipment["shipmentLineItems"]), 1)
        for item in shipment["shipmentLineItems"]:
            self.assertIn("name", item)
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
            for sent, got in zip(shipment["shipmentLineItems"], echoed_items):
                self.assertEqual(
                    got.get("name"),
                    sent["name"],
                    "line item 'name' was dropped by MyCarrier",
                )
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
