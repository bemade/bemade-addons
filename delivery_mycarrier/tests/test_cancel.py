"""Acceptance criteria — MyCarrier cancel shipment (v1 guided error)."""

from odoo.exceptions import UserError
from odoo.tools.misc import mute_logger

from .common import MyCarrierCommon


class TestMyCarrierCancel(MyCarrierCommon):

    @mute_logger("odoo.models.unlink")
    def test_cancel_raises_userror(self):
        picking = self.make_picking()
        picking.write(
            {
                "mycarrier_status": "booked",
                "mycarrier_shipment_id": "SHIP-XYZ",
                "carrier_tracking_ref": "PRO42",
            }
        )
        with self.assertRaises(UserError) as ctx:
            self.carrier.mycarrier_cancel_shipment(picking)
        msg = str(ctx.exception)
        self.assertIn(picking.name, msg)
        self.assertIn("PRO42", msg)
        self.assertIn("MyCarrier", msg)

    def test_cancel_does_not_mutate_state(self):
        picking = self.make_picking()
        picking.mycarrier_status = "booked"
        with self.assertRaises(UserError):
            self.carrier.mycarrier_cancel_shipment(picking)
        self.assertEqual(
            picking.mycarrier_status,
            "booked",
            "cancel UserError must not flip mycarrier_status; wait for webhook",
        )
