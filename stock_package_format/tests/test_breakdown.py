# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Breakdown -- Seeing the packages per format without digging.

Acceptance criteria
-------------------
B1   A flagged product (template and variant) carries the per-format
     breakdown of its stock: whole unopened packages per format, opened
     packages with their content, loose stock. It feeds the compact summary
     of the smart button and the popover on the On Hand quantity.
B2   The smart button opens « Stock by Package Format » filtered on the
     product, grouped by package type then lot.
B3   « On Hand » (action_open_quants) opens grouped by package type then lot
     for a flagged product; unchanged for other products.
B4   A quotation line of a flagged product lists the per-format counts of the
     product's FREE stock in the warehouse (unreserved whole packages per
     format, opened, loose), besides « N available · M to buy ».
B5   The product forms load with the smart button and the popovers.
"""

import json

from odoo.tests import Form

from .common import PackageFormatCase


class TestBreakdown(PackageFormatCase):
    def _mixed_stock(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        self._put_packages(self.uom_bag, 67, lot_name="L2")
        self._put_packages(self.uom_bulk, 1, lot_name="L3")
        opened = self._put_packages(self.uom_drum, 1, lot_name="L1", opened=True)
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock, -1.8, lot_id=self._lot("L1"), package_id=opened
        )
        self._put_loose(2.0, lot_name="L4")

    def test_b1_breakdown_on_product_and_template(self):
        self._mixed_stock()
        for record in (self.product, self.product.product_tmpl_id):
            summary = record.package_format_summary
            self.assertIn("2 × %s" % self.type_drum.name, summary)
            self.assertIn("67 × %s" % self.type_bag.name, summary)
            self.assertIn("1 × %s" % self.type_bulk.name, summary)
            self.assertIn("3.2", summary)
            self.assertIn("2 %s" % self.uom_ft3.name, summary)
            data = json.loads(record.package_format_breakdown)
            self.assertEqual(data["icon"], "fa-cubes")
            self.assertEqual(
                data["popoverTemplate"], "stock_package_format.BreakdownPopover"
            )
            rows = {(r["label"], r["opened"]): r for r in data["rows"]}
            self.assertEqual(rows[(self.type_drum.name, False)]["count"], 2)
            self.assertEqual(rows[(self.type_drum.name, False)]["qty"], "10 %s" % self.uom_ft3.name)
            self.assertEqual(rows[(self.type_bag.name, False)]["count"], 67)
            self.assertEqual(rows[(self.type_drum.name, True)]["count"], 1)
            self.assertEqual(rows[(self.type_drum.name, True)]["qty"], "3.2 %s" % self.uom_ft3.name)
            self.assertEqual(data["loose"], "2 %s" % self.uom_ft3.name)
        self.assertFalse(self.plain_product.package_format_breakdown)
        self.assertFalse(self.plain_product.package_format_summary)

    def test_b2_smart_button_opens_the_report(self):
        self._mixed_stock()
        for record in (self.product, self.product.product_tmpl_id):
            action = record.action_package_format_stock()
            self.assertEqual(action["res_model"], "stock.quant")
            self.assertEqual(action["context"]["group_by"], ["package_type_id", "lot_id"])
            quants = self.env["stock.quant"].search(action["domain"])
            self.assertEqual(quants.product_id, self.product)
            self.assertAlmostEqual(sum(quants.mapped("quantity")), self.product.qty_available)

    def test_b3_on_hand_grouped_for_flagged_products(self):
        for record in (self.product, self.product.product_tmpl_id):
            action = record.action_open_quants()
            self.assertEqual(action["context"]["group_by"], ["package_type_id", "lot_id"])
        action = self.plain_product.action_open_quants()
        self.assertNotIn("group_by", action.get("context") or {})

    def test_b4_sale_line_lists_free_stock_per_format(self):
        self._mixed_stock()
        # a delivery of 1 drum reserves one whole drum: it is no longer free
        self._delivery(1, self.uom_drum)
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    (0, 0, {
                        "product_id": self.product.id,
                        "product_uom_qty": 3,
                        "product_uom_id": self.uom_drum.id,
                    }),
                    (0, 0, {
                        "product_id": self.plain_product.id,
                        "product_uom_qty": 3,
                        "product_uom_id": self.uom_ft3.id,
                    }),
                ],
            }
        )
        line, plain_line = order.order_line
        self.assertIn("1 available", line.package_format_availability)
        free = line.package_format_free_stock
        self.assertIn("1 × %s" % self.type_drum.name, free)
        self.assertIn("67 × %s" % self.type_bag.name, free)
        self.assertIn("1 × %s" % self.type_bulk.name, free)
        self.assertIn("3.2", free)
        self.assertIn("2 %s" % self.uom_ft3.name, free)
        self.assertFalse(plain_line.package_format_free_stock)

    def test_b5_product_forms_load(self):
        self._mixed_stock()
        # Form loads the full views: the smart button, the On Hand popovers
        # and the fields they need must all be there.
        Form(self.product.product_tmpl_id)
        Form(self.product)
