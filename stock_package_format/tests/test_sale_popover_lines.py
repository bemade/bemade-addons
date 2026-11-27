# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Availability popover -- one packaging possibility per line.

Acceptance criteria
-------------------
P1   On a quotation line of a flagged product, the free stock per format
     lists one format per line (whole packages per format, then opened
     packages, then loose stock), not a run-on sentence.
P2   The proposal to open packages for a loose line starts with
     « Open to cover this line: » and lists one package format per line
     (« N × Type (Q uom) »).
P3   A single format still reads as one line under its heading.
P4   The availability popover template renders each of those lines as its
     own list item.
"""

from odoo import Command
from odoo.tools.misc import file_open

from .common import PackageFormatCase


class TestSalePopoverLines(PackageFormatCase):
    def _order(self, lines):
        return self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "product_uom_id": uom.id,
                        }
                    )
                    for qty, uom in lines
                ],
            }
        )

    def test_p1_free_stock_one_format_per_line(self):
        self._put_packages(self.uom_drum, 2, lot_name="L1")
        self._put_packages(self.uom_bag, 3, lot_name="L2")
        self._put_packages(self.uom_bulk, 1, lot_name="L3")
        opened = self._put_packages(self.uom_drum, 1, lot_name="L1", opened=True)
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.stock, -1.8, lot_id=self._lot("L1"), package_id=opened
        )
        self._put_loose(2.0, lot_name="L4")
        line = self._order([(1, self.uom_drum)]).order_line
        ft3 = self.uom_ft3.name
        self.assertEqual(
            line.package_format_free_stock.split("\n"),
            [
                "3 × %s" % self.type_bag.name,
                "1 × %s" % self.type_bulk.name,
                "2 × %s" % self.type_drum.name,
                "opened: 1 × %s (3.2 %s)" % (self.type_drum.name, ft3),
                "loose: 2 %s" % ft3,
            ],
        )

    def test_p2_proposal_one_format_per_line(self):
        # Nothing loose and no single format covers 50 ft³: every package is
        # proposed, bags and drum each on their own line.
        self._put_packages(self.uom_bag, 2, lot_name="L1")
        self._put_packages(self.uom_drum, 1, lot_name="L2")
        line = self._order([(50, self.uom_ft3)]).order_line
        ft3 = self.uom_ft3.name
        self.assertEqual(
            line.package_format_proposal.split("\n"),
            [
                "Open to cover this line:",
                "2 × %s (2 %s)" % (self.type_bag.name, ft3),
                "1 × %s (5 %s)" % (self.type_drum.name, ft3),
            ],
        )

    def test_p3_single_format(self):
        self._put_packages(self.uom_bag, 10, lot_name="L1")
        line = self._order([(3, self.uom_ft3)]).order_line
        self.assertEqual(line.package_format_free_stock, "10 × %s" % self.type_bag.name)
        self.assertEqual(
            line.package_format_proposal.split("\n"),
            [
                "Open to cover this line:",
                "3 × %s (3 %s)" % (self.type_bag.name, self.uom_ft3.name),
            ],
        )

    def test_p4_popover_lists_lines(self):
        with file_open(
            "stock_package_format/static/src/sale_qty_popover/"
            "qty_at_date_package_format.xml"
        ) as f:
            template = f.read()
        self.assertIn("package_format_free_stock.split('\\n')", template)
        self.assertIn("package_format_proposal.split('\\n')", template)
