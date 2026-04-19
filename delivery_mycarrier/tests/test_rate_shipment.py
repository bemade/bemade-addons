"""Acceptance criteria — MyCarrier rate shipment.

The ``mycarrier_rate_shipment(order)`` hook on ``delivery.carrier`` must:

1. Happy path (US-to-US LTL quote)
   - Build a rating payload carrying the carrier's ``locationId`` and one
     ``quoteUnits`` entry per pallet, each with a ``quoteCommodities``
     array covering every product on the sale order with its NMFC class.
   - POST the payload via ``MyCarrierRequest.rate``.
   - Return ``{'success': True, 'price': <amount>, 'error_message': '',
     'warning_message': False}`` with ``_apply_margins`` applied.

2. Non-serviceable destination — return ``success=False`` without raising.
3. API/transport error — return ``success=False`` with a user-safe message.
4. Currency conversion — quote currency converts to SO pricelist currency.
5. Margin application — ``base_price * (1 + margin) + fixed_margin``.
6. Missing location — return ``success=False`` with a guided message.
"""

from unittest.mock import patch

from odoo.addons.delivery_mycarrier.models.mycarrier_request import (
    MyCarrierRequestError,
)

from .common import MyCarrierCommon


RATE_RESPONSE_OK = {
    "rates": [
        {
            "carrierName": "Test LTL Co",
            "totalCost": 275.50,
            "currency": "USD",
            "transitDays": 3,
        }
    ]
}

RATE_RESPONSE_MULTI = {
    "rates": [
        {"carrierName": "Premium LTL", "totalCost": 410.00, "currency": "USD"},
        {"carrierName": "Budget LTL", "totalCost": 298.75, "currency": "USD"},
        {"carrierName": "Mid LTL", "totalCost": 325.00, "currency": "USD"},
    ]
}


def _patch_rate(response=None, *, exception=None):
    """Patch ``MyCarrierRequest.rate`` to return ``response`` or raise."""
    target = (
        "odoo.addons.delivery_mycarrier.models.mycarrier_request."
        "MyCarrierRequest.rate"
    )
    if exception is not None:
        return patch(target, side_effect=exception)
    return patch(target, return_value=response)


class TestMyCarrierRateShipment(MyCarrierCommon):

    def test_rate_happy_path(self):
        order = self.make_sale_order()
        with _patch_rate(RATE_RESPONSE_OK) as mocked:
            result = self.carrier.mycarrier_rate_shipment(order)

        self.assertTrue(mocked.called, "MyCarrierRequest.rate was not invoked")
        payload = mocked.call_args.args[0]
        self.assertEqual(
            payload.get("locationId"),
            self.carrier.mycarrier_location_id,
            "locationId missing from rating payload",
        )
        data = payload.get("data") or {}
        quote_units = data.get("quoteUnits") or []
        self.assertGreaterEqual(
            len(quote_units), 1, "rating payload must contain at least one quoteUnit"
        )
        commodities = [
            c for unit in quote_units for c in (unit.get("quoteCommodities") or [])
        ]
        classes = {c.get("commodityClass") for c in commodities}
        self.assertIn("70", classes, "product_pallet_a NMFC class missing")
        self.assertIn("125", classes, "product_pallet_b NMFC class missing")

        self.assertTrue(result["success"], f"rate failed: {result}")
        self.assertEqual(result["error_message"], "")
        self.assertAlmostEqual(result["price"], 275.50, places=2)

    def test_rate_picks_cheapest(self):
        order = self.make_sale_order()
        with _patch_rate(RATE_RESPONSE_MULTI):
            result = self.carrier.mycarrier_rate_shipment(order)
        self.assertTrue(result["success"])
        self.assertAlmostEqual(result["price"], 298.75, places=2)

    def test_rate_no_eligible_carriers(self):
        order = self.make_sale_order()
        with _patch_rate({"rates": []}):
            result = self.carrier.mycarrier_rate_shipment(order)
        self.assertFalse(result["success"])
        self.assertEqual(result["price"], 0.0)
        self.assertIn("no eligible carriers", result["error_message"].lower())

    def test_rate_api_error(self):
        order = self.make_sale_order()
        with _patch_rate(exception=MyCarrierRequestError("boom")):
            result = self.carrier.mycarrier_rate_shipment(order)
        self.assertFalse(result["success"])
        self.assertEqual(result["price"], 0.0)
        self.assertIn("boom", result["error_message"])
        self.assertNotIn(self.carrier.sudo().mycarrier_api_key, result["error_message"])

    def test_rate_missing_location_id(self):
        self.carrier.mycarrier_location_id = False
        order = self.make_sale_order()
        with _patch_rate(RATE_RESPONSE_OK) as mocked:
            result = self.carrier.mycarrier_rate_shipment(order)
        self.assertFalse(mocked.called, "Should not hit API when location missing")
        self.assertFalse(result["success"])
        self.assertEqual(result["price"], 0.0)
        self.assertIn("location", result["error_message"].lower())

    def test_rate_through_framework_applies_margin(self):
        self.carrier.write({"margin": 0.10, "fixed_margin": 25.0})
        order = self.make_sale_order()
        with _patch_rate(RATE_RESPONSE_OK):
            result = self.carrier.rate_shipment(order)
        self.assertTrue(result["success"])
        expected = 275.50 * 1.10 + 25.0
        self.assertAlmostEqual(result["price"], expected, places=2)
