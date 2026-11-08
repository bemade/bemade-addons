# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: each quotation line says how reliable its cost is, and why.

ACCEPTANCE CRITERIA
1. A line carries a confidence (firm / indicative / estimated / unknown) and a
   one-line reason made of the engine's evidence sentences.
2. A vendor price list in force with an end date gives Firm with its expiry.
3. A start-only supplier price older than the age window gives Estimated.
4. A product with no price at all gives Unknown.
5. Free stock in the ORDER's warehouse covers the line first: fully covered is
   Firm from stock; partly covered blends; stock in another warehouse or
   already reserved does not count.
6. Two lines of the same product on one order share the free stock rather
   than each counting all of it.
7. The quantity is converted to the product's unit of measure before costing.
8. Nothing is stored: changing a supplier price changes the indicator the next
   time it is read, on a quotation and on a confirmed order alike.
9. The tooltip payload carries the level, its label, the evidence, warnings
   and notes, and the unit cost formatted in the order's currency.
"""
from odoo.tests import tagged

from .common import SaleCostSourceCommon


@tagged("post_install", "-at_install")
class TestLineIndicator(SaleCostSourceCommon):
    def test_price_list_in_force_is_firm(self):
        end = self._ahead(months=2)
        self._seller(date_end=end)
        level, reason = self._read(self._line())
        self.assertEqual(level, "firm")
        self.assertEqual(reason, f"Firm. Vendor price list valid to {self._fmt(end)}.")

    def test_old_start_only_price_is_estimated(self):
        start = self._ago(9)
        self._seller(date_start=start)
        level, reason = self._read(self._line())
        self.assertEqual(level, "estimated")
        self.assertIn(self._fmt(start), reason)
        self.assertTrue(reason.startswith("Estimated."))

    def test_nothing_known_is_unknown(self):
        self.assertEqual(
            self._read(self._line()),
            ("unknown", "Unknown. No vendor price and no purchase history."),
        )

    def test_stock_in_the_order_warehouse_covers(self):
        self._stock(10)
        level, reason = self._read(self._line())
        self.assertEqual(level, "firm")
        self.assertTrue(reason.startswith("Firm. Covered from stock at"))

    def test_partial_stock_blends(self):
        self._stock(4)
        self._seller(date_start=self._ago(9))
        level, reason = self._read(self._line())
        self.assertEqual(level, "estimated")
        self.assertIn("4 of 10 covered from stock", reason)

    def test_other_warehouse_stock_does_not_count(self):
        other = self.env["stock.warehouse"].create(
            {"name": "Other Warehouse", "code": "OTH", "company_id": self.company.id}
        )
        self._stock(10, warehouse=other)
        self.assertEqual(self._read(self._line())[0], "unknown")

    def test_reserved_stock_is_not_free(self):
        self._stock(10)
        self._order([{"product_id": self.product.id, "product_uom_qty": 8}]).action_confirm()
        self.assertEqual(self._read(self._line())[0], "unknown")

    def test_lines_of_one_order_share_free_stock(self):
        self._stock(10)
        order = self._order(
            [
                {"product_id": self.product.id, "product_uom_qty": 6},
                {"product_id": self.product.id, "product_uom_qty": 6},
            ]
        )
        first, second = order.order_line
        self.assertEqual(self._read(first)[0], "firm")
        level, reason = self._read(second)
        self.assertEqual(level, "unknown")
        self.assertIn("4 of 6 covered from stock", reason)

    def test_quantity_in_line_uom(self):
        dozen = self.env.ref("uom.product_uom_dozen")
        self._stock(12)
        order = self._order(
            [{"product_id": self.product.id, "product_uom_qty": 1, "product_uom_id": dozen.id}]
        )
        self.assertEqual(self._read(order.order_line)[0], "firm")

    def test_indicator_is_live(self):
        seller = self._seller(date_start=self._ago(9))
        order = self._order()
        self.assertEqual(self._read(order.order_line)[0], "estimated")
        seller.date_start = self._ago(1)
        self.assertEqual(self._read(order.order_line)[0], "firm")
        order.action_confirm()
        seller.date_start = self._ago(9)
        self.assertEqual(self._read(order.order_line)[0], "estimated")

    def test_tooltip_payload(self):
        end = self._ahead(months=2)
        self._seller(date_end=end, price=15.0)
        line = self._line()
        self._read(line)
        payload = line.cost_source_explanation
        self.assertEqual(payload["level"], "firm")
        self.assertEqual(payload["level_label"], "Firm")
        self.assertEqual(payload["evidence"], [f"Firm. Vendor price list valid to {self._fmt(end)}."])
        self.assertEqual(payload["warnings"], [])
        self.assertEqual(payload["notes"], [])
        self.assertIn("15.00", payload["unit_cost"])
