# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Lowering a confirmed foreign-currency PO line after the exchange rate moved.

Acceptance criteria:

1. Line set to 0 after a rate change: the open receipt move is cancelled, and
   no return (move to the vendor) is created.
2. Partial decrease: the open receipt is reduced by the same quantity and keeps
   its original unit cost (Odoo's weighted average would distort it).
3. Successive decreases and several open moves at different costs behave the
   same way.
4. Quantity already received: the received part is untouched, the open
   backorder is reduced, and going below the received quantity is still
   refused, as in standard Odoo.
5. Setting off: standard behaviour, i.e. a return is created.
6. Negative moves that do not come from a purchase line are not affected.
"""

from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDecreaseIgnoreCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.purchase_decrease_ignore_cost = True
        eur = cls.env.ref("base.EUR")
        cls.foreign = (
            eur if cls.company.currency_id != eur else cls.env.ref("base.CAD")
        )
        cls.foreign.active = True
        cls.env["res.currency.rate"].search(
            [("currency_id", "=", cls.foreign.id)]
        ).unlink()
        cls.today = fields.Date.today()
        # The rate in force when the order is confirmed: yesterday's.
        cls._load_rate(cls.today - timedelta(days=1), 1.3804)
        cls.vendor = cls.env["res.partner"].create({"name": "Foreign Vendor"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Imported Part",
                "is_storable": True,
                "purchase_method": "receive",
                "supplier_taxes_id": [Command.clear()],
            }
        )

    @classmethod
    def _load_rate(cls, date, company_per_unit):
        """Load (or reload) the rate of the foreign currency for ``date``."""
        rate = cls.env["res.currency.rate"].search(
            [
                ("currency_id", "=", cls.foreign.id),
                ("company_id", "=", cls.company.id),
                ("name", "=", date),
            ]
        )
        vals = {"inverse_company_rate": company_per_unit}
        if rate:
            rate.write(vals)
        else:
            cls.env["res.currency.rate"].create(
                dict(
                    vals,
                    name=date,
                    currency_id=cls.foreign.id,
                    company_id=cls.company.id,
                )
            )

    def _confirm_po(self, qty=130, price=2.51):
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "currency_id": self.foreign.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_qty": qty,
                            "price_unit": price,
                        }
                    )
                ],
            }
        )
        po.button_confirm()
        return po

    def _open_moves(self, line):
        return line.move_ids.filtered(
            lambda m: m.state not in ("done", "cancel")
            and m.location_dest_id.usage == "internal"
        )

    def _returns(self, line):
        return line.move_ids.filtered(
            lambda m: m.state != "cancel" and m.location_dest_id.usage == "supplier"
        )

    def _receive(self, line, qty):
        move = self._open_moves(line)
        move.quantity = qty
        move.picked = True
        res = move.picking_id.button_validate()
        if isinstance(res, dict) and res.get("res_model"):
            wizard = Form(
                self.env[res["res_model"]].with_context(**res["context"])
            ).save()
            wizard.process()

    def test_set_to_zero_cancels_receipt(self):
        po = self._confirm_po()
        line = po.order_line
        receipt_move = self._open_moves(line)
        self.assertEqual(receipt_move.price_unit, 3.46)
        self._load_rate(self.today, 1.3812)  # 2.51 now converts to 3.47

        line.product_qty = 0

        self.assertEqual(receipt_move.state, "cancel")
        self.assertFalse(self._open_moves(line))
        self.assertFalse(self._returns(line))

    def test_partial_decrease_keeps_cost(self):
        po = self._confirm_po()
        line = po.order_line
        self._load_rate(self.today, 1.3812)

        line.product_qty = 30

        move = self._open_moves(line)
        self.assertEqual(move.product_uom_qty, 30)
        self.assertEqual(move.price_unit, 3.46)
        self.assertFalse(self._returns(line))

    def test_decrease_to_one_keeps_cost(self):
        """Odoo's weighted average would give (130*3.46 - 129*3.47)/1 = 2.17."""
        po = self._confirm_po()
        line = po.order_line
        self._load_rate(self.today, 1.3812)

        line.product_qty = 1

        move = self._open_moves(line)
        self.assertEqual(move.product_uom_qty, 1)
        self.assertEqual(move.price_unit, 3.46)
        self.assertFalse(self._returns(line))

    def test_successive_decreases(self):
        po = self._confirm_po()
        line = po.order_line
        self._load_rate(self.today, 1.3812)
        line.product_qty = 100
        self._load_rate(self.today, 1.3830)  # reloaded again: 3.47

        line.product_qty = 60

        move = self._open_moves(line)
        self.assertEqual(move.product_uom_qty, 60)
        self.assertEqual(move.price_unit, 3.46)
        self.assertFalse(self._returns(line))

    def test_two_open_moves_at_different_costs(self):
        po = self._confirm_po(qty=100)
        line = po.order_line
        self._load_rate(self.today, 1.3812)
        line.product_qty = 150  # the extra 50 is a second move at 3.47
        self.assertEqual(
            sorted(self._open_moves(line).mapped("price_unit")), [3.46, 3.47]
        )
        original_costs = {m.id: m.price_unit for m in self._open_moves(line)}

        line.product_qty = 20

        moves = self._open_moves(line)
        self.assertEqual(sum(moves.mapped("product_uom_qty")), 20)
        for move in moves:
            self.assertEqual(move.price_unit, original_costs[move.id])
        self.assertFalse(self._returns(line))

    def test_received_quantity_is_kept(self):
        po = self._confirm_po()
        line = po.order_line
        self._receive(line, 50)
        backorder_move = self._open_moves(line)
        self.assertEqual(backorder_move.product_uom_qty, 80)
        self._load_rate(self.today, 1.3812)

        line.product_qty = 50

        self.assertEqual(backorder_move.state, "cancel")
        self.assertEqual(line.qty_received, 50)
        self.assertFalse(self._returns(line))
        with self.assertRaises(UserError):
            line.product_qty = 40

    def test_setting_off_keeps_standard_return(self):
        self.company.purchase_decrease_ignore_cost = False
        po = self._confirm_po()
        line = po.order_line
        receipt_move = self._open_moves(line)
        self._load_rate(self.today, 1.3812)

        line.product_qty = 0

        self.assertEqual(receipt_move.product_uom_qty, 130)
        self.assertEqual(self._returns(line).product_uom_qty, 130)

    def test_negative_move_without_purchase_line_untouched(self):
        picking_type = self.env.ref("stock.picking_type_in")
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            }
        )
        move_vals = {
            "name": self.product.name,
            "product_id": self.product.id,
            "picking_id": picking.id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
        }
        pos = self.env["stock.move"].create(
            dict(move_vals, product_uom_qty=10, price_unit=5.0)
        )
        pos._action_confirm()
        neg = self.env["stock.move"].create(
            dict(move_vals, product_uom_qty=-4, price_unit=6.0)
        )

        neg._action_confirm()

        self.assertEqual(pos.product_uom_qty, 10)
        self.assertTrue(neg.exists())
