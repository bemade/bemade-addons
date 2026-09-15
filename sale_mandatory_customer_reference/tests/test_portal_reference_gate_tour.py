# License: LGPL-3
# Copyright 2026 Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
Portal gate: the customer cannot open the signature dialog until the PO
reference is saved, and does not need to reload the page afterwards.

Acceptance criteria (tour):
- AC1: reference empty -> warning visible, Accept & Sign rendered disabled,
  no signature dialog.
- AC2: enter + save the reference -> buttons enabled immediately.
- AC3: Accept & Sign then opens the signature dialog.
"""
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("post_install", "-at_install")
class TestPortalReferenceGateTour(HttpCase):
    def test_portal_reference_gate_tour(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_mandatory_customer_reference.enforce_customer_reference", True
        )
        partner = self.env["res.partner"].create(
            {"name": "Gate Tour Customer", "email": "gate@example.com"}
        )
        product = self.env["product.product"].create(
            {"name": "Gate Tour Product", "type": "consu"}
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "require_signature": True,
                "require_payment": False,
                "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1})],
            }
        )
        order.action_quotation_sent()
        order._portal_ensure_token()
        self.assertTrue(order._portal_reference_missing())

        self.start_tour(
            f"/my/orders/{order.id}?access_token={order.access_token}",
            "sale_mandatory_customer_reference_portal_gate",
            login=None,
        )

        order.invalidate_recordset()
        self.assertEqual(order.client_order_ref, "PO-TOUR-1")
        self.assertFalse(order._portal_reference_missing())
