# License: LGPL-3
# Copyright 2026 Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
Portal "Accept & Sign" must fail cleanly when the customer reference is missing.

Acceptance criteria:
- AC1: With enforce_customer_reference=True and no client_order_ref, a public
  POST to /my/orders/<id>/accept returns a JSON-RPC *result* carrying an
  ``error`` message (not a JSON-RPC exception). The portal SignatureForm has no
  try/catch around its RPC, so an exception leaves the button spinning forever.
- AC2: In that case nothing is written: no signature, state unchanged.
- AC3: With a client_order_ref set, the same call signs and confirms the order.
"""
import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase
from odoo.tools.misc import mute_logger

# 1x1 transparent PNG, base64 payload only (what the signature widget sends)
SIGNATURE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)


@tagged("post_install", "-at_install")
class TestPortalAccept(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(
            "sale_mandatory_customer_reference.enforce_customer_reference", True
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Portal Accept Customer", "email": "accept@example.com"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Portal Accept Product", "type": "consu"}
        )

    def _make_order(self, reference=False):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "require_signature": True,
                "require_payment": False,
                "client_order_ref": reference,
                "order_line": [
                    (0, 0, {"product_id": self.product.id, "product_uom_qty": 1})
                ],
            }
        )
        order.action_quotation_sent()
        order._portal_ensure_token()
        return order

    def _accept(self, order):
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "call",
                "id": 1,
                "params": {
                    "access_token": order.access_token,
                    "name": "Jane Portal",
                    "signature": SIGNATURE_B64,
                },
            }
        )
        resp = self.url_open(
            f"/my/orders/{order.id}/accept",
            data=payload.encode(),
            headers={"Content-Type": "application/json"},
        )
        return resp.json()

    @mute_logger("odoo.addons.base.models.ir_model")
    def test_accept_without_reference_returns_clean_error(self):
        order = self._make_order()
        body = self._accept(order)
        self.assertNotIn(
            "error", body, f"JSON-RPC exception instead of a clean result: {body}"
        )
        result = body["result"]
        self.assertIn("error", result, f"Expected an error message, got {result}")
        self.assertIn("Customer reference", result["error"])
        order.invalidate_recordset()
        self.assertEqual(order.state, "sent")
        self.assertFalse(order.signature)
        self.assertFalse(order.signed_by)

    @mute_logger("odoo.addons.base.models.ir_model")
    def test_accept_with_reference_confirms(self):
        order = self._make_order(reference="PO-777")
        body = self._accept(order)
        self.assertNotIn("error", body, f"Unexpected JSON-RPC exception: {body}")
        self.assertNotIn("error", body["result"], body["result"])
        order.invalidate_recordset()
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.signed_by, "Jane Portal")
