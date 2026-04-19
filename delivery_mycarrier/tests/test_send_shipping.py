"""Acceptance criteria — MyCarrier send shipping (order booking).

See module docstring of :mod:`delivery_mycarrier` for the full contract.
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tools.misc import mute_logger

from odoo.addons.delivery_mycarrier.models.mycarrier_request import (
    MyCarrierRequestError,
)

from .common import MyCarrierCommon


ORDER_RESPONSE_OK = {
    "status": "queued",
    "orders": [
        {
            "quoteReferenceID": "WH/OUT/00001",
            "quoteId": "Q-123",
            "orderId": "O-456",
        }
    ],
}


def _patch_create_order(response=None, *, exception=None):
    target = (
        "odoo.addons.delivery_mycarrier.models.mycarrier_request."
        "MyCarrierRequest.create_order"
    )
    if exception is not None:
        return patch(target, side_effect=exception)
    return patch(target, return_value=response)


class TestMyCarrierSendShipping(MyCarrierCommon):

    def test_payload_shape(self):
        picking = self.make_picking()
        with _patch_create_order(ORDER_RESPONSE_OK) as mocked:
            self.carrier.mycarrier_send_shipping(picking)
        self.assertTrue(mocked.called)
        payload = mocked.call_args.args[0]
        orders = payload.get("orders") or []
        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order.get("locationId"), self.carrier.mycarrier_location_id)
        self.assertEqual(order.get("paymentDirection"), "Prepaid")
        self.assertEqual(order.get("readyToDispatch"), "Yes")
        self.assertEqual(order.get("quoteReferenceID"), picking.name)
        self.assertEqual(order.get("pickupDate"), "05-01-2026")

        dest = order.get("destination") or {}
        self.assertEqual(dest.get("city"), "Columbia")
        self.assertEqual(dest.get("state"), "SC")
        self.assertEqual(dest.get("zip"), "29201")

        quote_units = order.get("quoteUnits") or []
        self.assertGreaterEqual(len(quote_units), 1)
        classes = {
            c.get("commodityClass")
            for u in quote_units
            for c in (u.get("quoteCommodities") or [])
        }
        self.assertIn("70", classes)
        self.assertIn("125", classes)

    def test_async_return_contract(self):
        picking = self.make_picking()
        with _patch_create_order(ORDER_RESPONSE_OK):
            result = self.carrier.mycarrier_send_shipping(picking)
        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertIn("exact_price", entry)
        self.assertIn("tracking_number", entry)
        self.assertTrue(entry["tracking_number"].startswith("MYCARRIER-PENDING-"))
        self.assertIn(picking.name, entry["tracking_number"])

    def test_stores_identifiers(self):
        picking = self.make_picking()
        response = {
            "status": "queued",
            "orders": [
                {
                    "quoteReferenceID": picking.name,
                    "quoteId": "Q-123",
                    "orderId": "O-456",
                }
            ],
        }
        with _patch_create_order(response):
            self.carrier.mycarrier_send_shipping(picking)
        self.assertEqual(picking.mycarrier_order_id, "O-456")
        self.assertEqual(picking.mycarrier_quote_id, "Q-123")
        self.assertEqual(picking.mycarrier_status, "queued")

    @mute_logger("odoo.addons.delivery_mycarrier.models.mycarrier_request")
    def test_api_error_raises_userror(self):
        picking = self.make_picking()
        with _patch_create_order(exception=MyCarrierRequestError("bad creds")):
            with self.assertRaises(UserError) as ctx:
                self.carrier.mycarrier_send_shipping(picking)
        self.assertIn("bad creds", str(ctx.exception))
        self.assertNotIn(
            self.carrier.sudo().mycarrier_api_key, str(ctx.exception)
        )

    def test_missing_destination_address_raises_before_api(self):
        picking = self.make_picking()
        picking.partner_id.write({"city": False, "zip": False})
        with _patch_create_order(ORDER_RESPONSE_OK) as mocked:
            with self.assertRaises(UserError) as ctx:
                self.carrier.mycarrier_send_shipping(picking)
        self.assertFalse(mocked.called, "Must not call API when address invalid")
        msg = str(ctx.exception).lower()
        self.assertTrue("city" in msg or "zip" in msg)

    def test_multi_picking(self):
        picking_a = self.make_picking()
        picking_b = self.make_picking()
        response = {
            "status": "queued",
            "orders": [
                {
                    "quoteReferenceID": picking_a.name,
                    "quoteId": "Q-A",
                    "orderId": "O-A",
                },
                {
                    "quoteReferenceID": picking_b.name,
                    "quoteId": "Q-B",
                    "orderId": "O-B",
                },
            ],
        }
        pickings = picking_a + picking_b
        with _patch_create_order(response) as mocked:
            result = self.carrier.mycarrier_send_shipping(pickings)
        self.assertEqual(mocked.call_count, 1, "Must batch in a single request")
        payload = mocked.call_args.args[0]
        self.assertEqual(len(payload.get("orders") or []), 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(picking_a.mycarrier_order_id, "O-A")
        self.assertEqual(picking_b.mycarrier_order_id, "O-B")

    def test_ready_to_dispatch_no(self):
        self.carrier.mycarrier_ready_to_dispatch = False
        picking = self.make_picking()
        with _patch_create_order(ORDER_RESPONSE_OK) as mocked:
            self.carrier.mycarrier_send_shipping(picking)
        payload = mocked.call_args.args[0]
        self.assertEqual(payload["orders"][0].get("readyToDispatch"), "No")
