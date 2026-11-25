# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""UC5b -- Raising the quantity of a confirmed sale line in a format.

Acceptance criteria
-------------------
*    Raising a confirmed line of 5 × drum (2 drums were free, 3 bought) to 7
     buys the 2 new drums: the RFQ line linked to the sale line goes from 3 to
     5 × drum.
*    When the linked RFQ is already confirmed, the 2 drums go on a new RFQ
     line in the drum unit, linked to the sale line; the confirmed one stays.
*    When enough whole drums are free in stock, nothing is bought.
*    Same with a two-step delivery (pick + ship).
*    Decreasing the quantity leaves the RFQ untouched (as in core Odoo).
*    Lines of unflagged products and lines in the base unit buy nothing more
     than core Odoo does.
*    The new shortfall is bought only once: the core procurement for the
     delta never buys it a second time.
"""

from odoo.fields import Command

from .common import PackageFormatCase


class TestSaleQtyRaise(PackageFormatCase):
    def _confirmed_order(self, qty, uom, product=None):
        order = self.env["sale.order"].create(
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
                ],
            }
        )
        order.action_confirm()
        return order

    def _purchase_lines(self, product=None):
        return self.env["purchase.order.line"].search(
            [("product_id", "=", (product or self.product).id)]
        )

    def _rfq_lines(self, sale_line):
        return self.env["purchase.order.line"].search(
            [("sale_line_id", "=", sale_line.id)]
        )

    def test_raise_extends_the_linked_rfq_line(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        order = self._confirmed_order(5, self.uom_drum)
        line = order.order_line
        rfq_line = self._rfq_lines(line)
        self.assertEqual(rfq_line.product_qty, 3)
        line.product_uom_qty = 7
        self.assertEqual(self._rfq_lines(line), rfq_line)
        self.assertEqual(rfq_line.product_qty, 5)
        self.assertEqual(rfq_line.product_uom_id, self.uom_drum)
        self.assertEqual(self._purchase_lines(), rfq_line)
        self.assertEqual(order.picking_ids.move_ids.product_uom_qty, 35)

    def test_raise_after_rfq_confirmed_buys_on_a_new_line(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        order = self._confirmed_order(5, self.uom_drum)
        line = order.order_line
        first = self._rfq_lines(line)
        first.order_id.button_confirm()
        line.product_uom_qty = 7
        self.assertEqual(first.product_qty, 3)
        new = self._rfq_lines(line) - first
        self.assertEqual(len(new), 1)
        self.assertEqual(new.product_qty, 2)
        self.assertEqual(new.product_uom_id, self.uom_drum)
        self.assertNotEqual(new.order_id, first.order_id)
        self.assertEqual(self._purchase_lines(), first | new)

    def test_raise_with_two_step_delivery(self):
        self.warehouse.delivery_steps = "pick_ship"
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        order = self._confirmed_order(5, self.uom_drum)
        line = order.order_line
        rfq_line = self._rfq_lines(line)
        self.assertEqual(rfq_line.product_qty, 3)
        line.product_uom_qty = 7
        self.assertEqual(rfq_line.product_qty, 5)
        self.assertEqual(self._purchase_lines(), rfq_line)

    def test_raise_with_enough_free_drums_buys_nothing(self):
        self._put_packages(self.uom_drum, 7, lot_name="L1")
        order = self._confirmed_order(5, self.uom_drum)
        line = order.order_line
        self.assertFalse(self._rfq_lines(line))
        line.product_uom_qty = 7
        self.assertFalse(self._purchase_lines())

    def test_raise_partly_covered_by_free_drums(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        order = self._confirmed_order(5, self.uom_drum)
        line = order.order_line
        # One more drum arrives in stock, unreserved.
        self._put_packages(self.uom_drum, 1, lot_name="L2")
        line.product_uom_qty = 7
        self.assertEqual(self._rfq_lines(line).product_qty, 4)

    def test_decrease_leaves_the_rfq_alone(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        order = self._confirmed_order(5, self.uom_drum)
        line = order.order_line
        rfq_line = self._rfq_lines(line)
        line.product_uom_qty = 3
        self.assertEqual(rfq_line.product_qty, 3)
        self.assertEqual(self._purchase_lines(), rfq_line)

    def test_unflagged_and_base_unit_lines_unchanged(self):
        self._put_packages(self.uom_drum, 1, lot_name="L1")
        order = self._confirmed_order(2, self.uom_drum, self.plain_product)
        order.order_line.product_uom_qty = 4
        self.assertFalse(self._purchase_lines(self.plain_product))
        loose = self._confirmed_order(3, self.uom_ft3)
        loose.order_line.product_uom_qty = 8
        self.assertFalse(self._purchase_lines())

    def test_new_format_line_on_confirmed_order_buys_shortfall(self):
        """A drum line ADDED to a confirmed order buys its shortfall too."""
        self._put_packages(self.uom_drum, 1, lot_name="L1")
        order = self._confirmed_order(1, self.uom_drum)
        self.assertFalse(self._rfq_lines(order.order_line))
        order.write(
            {
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 3,
                            "product_uom_id": self.uom_drum.id,
                        }
                    )
                ]
            }
        )
        new_line = order.order_line[1:]
        rfq_line = self._rfq_lines(new_line)
        self.assertEqual(len(rfq_line), 1)
        self.assertEqual(rfq_line.product_qty, 3)
        self.assertEqual(rfq_line.product_uom_id, self.uom_drum)
        self.assertEqual(self._purchase_lines(), rfq_line)

    def test_confirmed_loose_line_shows_open_proposal(self):
        """A confirmed line in the base unit that nothing loose covers shows
        the delivery's « open » proposal on the sale line."""
        self._put_packages(self.uom_bag, 5, lot_name="L1")
        order = self._confirmed_order(3, self.uom_ft3)
        line = order.order_line
        self.assertTrue(line.package_format_proposal)
        self.assertIn("3 ×", line.package_format_proposal)
        self.assertIn(self.type_bag.name, line.package_format_proposal)
