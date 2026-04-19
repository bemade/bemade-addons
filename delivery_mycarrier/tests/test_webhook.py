"""Acceptance criteria — MyCarrier inbound webhook handler.

These exercise ``delivery.carrier._mycarrier_handle_webhook`` directly.
The controller is a thin shim (auth + JSON parse) and is not exercised
here; its unit tests would require ``HttpCase`` which needs ``workers=0``.
"""

from unittest.mock import patch

from .common import MyCarrierCommon


class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def _patch_urlopen(bol=b"%PDF-BOL", label=b"%PDF-LABEL"):
    def fake(url, *args, **kwargs):
        if "bol" in url.lower():
            return _FakeResponse(bol)
        return _FakeResponse(label)
    return patch(
        "odoo.addons.delivery_mycarrier.models.delivery_carrier.urlopen",
        side_effect=fake,
    )


class TestMyCarrierWebhook(MyCarrierCommon):

    def _seed_picking(self, quote_id="Q-123", order_id="O-456"):
        picking = self.make_picking()
        picking.write(
            {
                "mycarrier_quote_id": quote_id,
                "mycarrier_order_id": order_id,
                "mycarrier_status": "queued",
            }
        )
        return picking

    # ---- correlation ----

    def test_unmatched_event_returns_ignored(self):
        status = self.carrier._mycarrier_handle_webhook(
            "shipment.created", {"QuoteId": "does-not-exist"}
        )
        self.assertEqual(status, "ignored")

    def test_unknown_event_type_returns_ignored(self):
        picking = self._seed_picking()
        status = self.carrier._mycarrier_handle_webhook(
            "shipment.whatever", {"QuoteId": picking.mycarrier_quote_id}
        )
        self.assertEqual(status, "ignored")
        self.assertEqual(picking.mycarrier_status, "queued")

    def test_correlate_by_quote_id(self):
        picking = self._seed_picking(quote_id="Q-AAA")
        with _patch_urlopen():
            self.carrier._mycarrier_handle_webhook(
                "shipment.created",
                {
                    "QuoteId": "Q-AAA",
                    "CarrierPRONumber": "PRO1",
                    "TotalCost": 100.0,
                },
            )
        self.assertEqual(picking.mycarrier_status, "booked")

    def test_correlate_by_picking_name(self):
        picking = self._seed_picking(quote_id=False, order_id=False)
        with _patch_urlopen():
            self.carrier._mycarrier_handle_webhook(
                "shipment.created",
                {
                    "CustomerBOLNumber": picking.name,
                    "CarrierPRONumber": "PRO2",
                    "TotalCost": 150.0,
                },
            )
        self.assertEqual(picking.mycarrier_status, "booked")
        self.assertEqual(picking.carrier_tracking_ref, "PRO2")

    def test_correlate_by_order_id(self):
        picking = self._seed_picking(quote_id=False, order_id="O-BBB")
        with _patch_urlopen():
            self.carrier._mycarrier_handle_webhook(
                "shipment.created",
                {
                    "orderId": "O-BBB",
                    "CarrierPRONumber": "PRO3",
                    "TotalCost": 200.0,
                },
            )
        self.assertEqual(picking.mycarrier_status, "booked")

    # ---- shipment.created ----

    def test_shipment_created_full_payload(self):
        picking = self._seed_picking()
        payload = {
            "QuoteId": picking.mycarrier_quote_id,
            "ShipmentId": "SHIP-789",
            "CarrierPRONumber": "PRO1234567",
            "CarrierName": "Best LTL",
            "TotalCost": 312.45,
            "BOLLink": "https://mycarrier.example.com/bol/abc",
            "LabelLink": "https://mycarrier.example.com/label/abc",
        }
        with _patch_urlopen():
            self.carrier._mycarrier_handle_webhook("shipment.created", payload)

        self.assertEqual(picking.carrier_tracking_ref, "PRO1234567")
        self.assertEqual(picking.mycarrier_shipment_id, "SHIP-789")
        self.assertAlmostEqual(picking.carrier_price, 312.45, places=2)
        self.assertEqual(picking.mycarrier_status, "booked")
        self.assertEqual(
            picking.mycarrier_bol_url, "https://mycarrier.example.com/bol/abc"
        )
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "stock.picking"), ("res_id", "=", picking.id)]
        )
        names = attachments.mapped("name")
        self.assertIn("MyCarrier-BOL-PRO1234567.pdf", names)
        self.assertIn("MyCarrier-Label-PRO1234567.pdf", names)

    def test_shipment_created_is_idempotent(self):
        picking = self._seed_picking()
        payload = {
            "QuoteId": picking.mycarrier_quote_id,
            "CarrierPRONumber": "PRO1234567",
            "TotalCost": 312.45,
            "BOLLink": "https://mycarrier.example.com/bol/abc",
            "LabelLink": "https://mycarrier.example.com/label/abc",
        }
        with _patch_urlopen():
            self.carrier._mycarrier_handle_webhook("shipment.created", payload)
            self.carrier._mycarrier_handle_webhook("shipment.created", payload)
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "stock.picking"),
                ("res_id", "=", picking.id),
                ("name", "like", "MyCarrier-"),
            ]
        )
        self.assertEqual(len(attachments), 2)

    # ---- tracking.updated ----

    def test_tracking_status_mapping(self):
        picking = self._seed_picking()
        for code, expected in [
            (0, "booked"),
            (1, "picked_up"),
            (2, "in_transit"),
            (3, "out_for_delivery"),
            (4, "delivered"),
        ]:
            self.carrier._mycarrier_handle_webhook(
                "shipment.tracking.updated",
                {
                    "QuoteId": picking.mycarrier_quote_id,
                    "StatusCode": code,
                    "TrackingHistory": [
                        {
                            "StatusDescription": f"status {code}",
                            "StatusDate": "2026-05-02",
                        }
                    ],
                },
            )
            self.assertEqual(picking.mycarrier_status, expected)

    def test_tracking_exception(self):
        picking = self._seed_picking()
        self.carrier._mycarrier_handle_webhook(
            "shipment.tracking.updated",
            {
                "QuoteId": picking.mycarrier_quote_id,
                "IsStatusException": True,
                "StatusCode": 2,
            },
        )
        self.assertEqual(picking.mycarrier_status, "exception")

    # ---- shipment.canceled ----

    def test_shipment_canceled(self):
        picking = self._seed_picking()
        self.carrier._mycarrier_handle_webhook(
            "shipment.canceled",
            {
                "QuoteId": picking.mycarrier_quote_id,
                "IsCanceled": True,
                "ShipmentPriceDetails": [
                    {"Description": "Cancellation fee", "Amount": "25.00"}
                ],
            },
        )
        self.assertEqual(picking.mycarrier_status, "canceled")
