# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""UC4, UC5, UC7 (sale side) -- Quoting in a format and buying the balance.

Acceptance criteria
-------------------
UC4  A quotation line of 2 × drum with 3 drums + 40 bags in stock shows « 2
     available » (other formats, opened and loose stock do not count) and
     nothing to buy; confirming reserves 2 whole drums.
UC5  A quotation line of 5 × drum with 2 drums + 40 bags shows « 2 available ·
     3 to buy ». Confirming creates an RFQ line of 3 × drum (the format unit)
     linked to the sale line. A reordering rule in the base unit never merges
     into that line, and its own need does not net it away. Receiving the RFQ
     gives 3 drum packages and the delivery then holds 5 whole drums.
*    Two lines of the same format on one order share the free packages.
*    Lines of unflagged products, and lines in the base unit, buy nothing.
UC7  A quotation line of 3 ft³ (base unit) on a flagged product with no
     opened package proposes opening the smallest covering package.
"""

from odoo.fields import Command

from .common import PackageFormatCase


class TestSaleFormatAvailability(PackageFormatCase):
    def _order(self, lines):
        return self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": (product or self.product).id,
                            "product_uom_qty": qty,
                            "product_uom_id": uom.id,
                        }
                    )
                    for qty, uom, product in lines
                ],
            }
        )

    def _rfq_lines(self, sale_line):
        return self.env["purchase.order.line"].search(
            [("sale_line_id", "=", sale_line.id)]
        )

    def test_uc4_quote_drums_available(self):
        self._put_packages(self.uom_drum, 3, lot_name="L1")
        self._put_packages(self.uom_bag, 40, lot_name="L2")
        order = self._order([(2, self.uom_drum, None)])
        line = order.order_line
        self.assertEqual(line.package_format_free_count, 3)
        self.assertEqual(line.package_format_to_buy, 0)
        self.assertIn("2", line.package_format_availability)
        order.action_confirm()
        move = order.picking_ids.move_ids
        self.assertEqual(move.packaging_uom_id, self.uom_drum)
        self.assertEqual(move.product_qty, 10)
        self.assertEqual(move.quantity, 10)
        self.assertEqual(len(move.move_line_ids.package_id), 2)
        self.assertEqual(move.move_line_ids.package_id.package_type_id, self.type_drum)
        self.assertFalse(self._rfq_lines(line))

    def test_uc5_buy_the_balance_in_the_format(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        self._put_packages(self.uom_bag, 40, lot_name="L2")
        order = self._order([(5, self.uom_drum, None)])
        line = order.order_line
        self.assertEqual(line.package_format_free_count, 2)
        self.assertEqual(line.package_format_to_buy, 3)
        self.assertIn("3", line.package_format_availability)
        order.action_confirm()
        rfq_line = self._rfq_lines(line)
        self.assertEqual(len(rfq_line), 1)
        self.assertEqual(rfq_line.product_uom_id, self.uom_drum)
        self.assertEqual(rfq_line.product_qty, 3)
        delivery = order.picking_ids
        self.assertEqual(delivery.move_ids.quantity, 10)

        # A base-unit reordering rule that needs stock does not merge into it.
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product.id,
                "location_id": self.stock.id,
                "warehouse_id": self.warehouse.id,
                "product_min_qty": 60,
                "product_max_qty": 80,
                "trigger": "auto",
            }
        )
        orderpoint._procure_orderpoint_confirm(company_id=self.company)
        self.assertEqual(rfq_line.product_qty, 3)
        self.assertEqual(rfq_line.product_uom_id, self.uom_drum)
        op_line = self.env["purchase.order.line"].search(
            [("product_id", "=", self.product.id), ("id", "!=", rfq_line.id)]
        )
        self.assertEqual(len(op_line), 1)
        # forecast: 50 on hand + 15 incoming (drums) + 0 - 25 outgoing = 40
        self.assertAlmostEqual(
            op_line.product_uom_id._compute_quantity(op_line.product_qty, self.uom_ft3),
            40,
        )

        # Receive: the 3 drums become 3 packages, the delivery takes 5 drums.
        purchase = rfq_line.order_id
        purchase.button_confirm()
        receipt = purchase.picking_ids
        action = receipt.button_validate()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        for row in wizard.line_ids:
            row.lot_name = "L7"
        wizard.action_confirm()
        self.assertEqual(receipt.state, "done")
        drum_rows = self.env["stock.quant"].search(
            [
                ("product_id", "=", self.product.id),
                ("package_id.package_type_id", "=", self.type_drum.id),
                ("lot_id.name", "=", "L7"),
            ]
        )
        self.assertEqual(len(drum_rows), 3)
        self.assertEqual(delivery.move_ids.quantity, 25)
        self.assertEqual(len(delivery.move_ids.move_line_ids.package_id), 5)

    def test_uc5_chained_customer_move_still_buys(self):
        """Multi-step delivery: the sale line's move toward the customer is
        make_to_order inside the warehouse (chained to the pick). That is not
        an MTO route: the format shortfall is still bought."""
        self.warehouse.delivery_steps = "pick_ship"
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        order = self._order([(5, self.uom_drum, None)])
        line = order.order_line
        plan = line._package_format_buy_plan()
        order.action_confirm()
        self._rfq_lines(line).unlink()
        line.move_ids.procure_method = "make_to_order"
        line._package_format_buy(plan)
        rfq_line = self._rfq_lines(line)
        self.assertEqual(rfq_line.product_qty, 3)
        self.assertEqual(rfq_line.product_uom_id, self.uom_drum)

    def test_two_lines_share_the_free_packages(self):
        self._put_packages(self.uom_drum, 3, lot_name="L1")
        order = self._order([(2, self.uom_drum, None), (2, self.uom_drum, None)])
        first, second = order.order_line
        order.action_confirm()
        self.assertFalse(self._rfq_lines(first))
        self.assertEqual(self._rfq_lines(second).product_qty, 1)

    def test_unflagged_and_loose_lines_buy_nothing(self):
        self._put_packages(self.uom_drum, 1, lot_name="L1")
        order = self._order(
            [(3, self.uom_ft3, None), (2, self.uom_drum, self.plain_product)]
        )
        self.assertFalse(order.order_line[1].package_format_availability)
        order.action_confirm()
        self.assertFalse(self._rfq_lines(order.order_line[0]))
        self.assertFalse(self._rfq_lines(order.order_line[1]))

    def test_uc7_quote_loose_proposes_opening(self):
        self._put_packages(self.uom_bag, 10, lot_name="L1")
        self._put_packages(self.uom_drum, 1, lot_name="L2")
        order = self._order([(3, self.uom_ft3, None)])
        line = order.order_line
        self.assertTrue(line.package_format_proposal)
        self.assertIn(self.type_drum.name, line.package_format_proposal)
