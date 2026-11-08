# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: lines whose cost is not a purchasing question carry no indicator.

ACCEPTANCE CRITERIA
1. Services, non-storable goods, sections and notes carry no indicator
   (confidence and reason empty, no tooltip payload).
2. A line with a zero or negative quantity carries no indicator.
3. Excluded lines are not counted in the order summary.
"""
from odoo.tests import tagged

from .common import SaleCostSourceCommon


@tagged("post_install", "-at_install")
class TestExclusions(SaleCostSourceCommon):
    def test_excluded_lines(self):
        service = self.env["product.product"].create({"name": "Service", "type": "service"})
        consumable = self.env["product.product"].create(
            {"name": "Consumable", "type": "consu", "is_storable": False}
        )
        order = self._order(
            [
                {"product_id": service.id},
                {"product_id": consumable.id},
                {"product_id": self.product.id, "product_uom_qty": 0},
                {"product_id": self.product.id, "product_uom_qty": -2},
                {"display_type": "line_section", "name": "Section", "product_uom_qty": 0},
                {"display_type": "line_note", "name": "Note", "product_uom_qty": 0},
            ]
        )
        for line in order.order_line:
            self.assertEqual(self._read(line), (False, False), line.name)
            self.assertFalse(line.cost_source_explanation)
        self.assertFalse(order.cost_source_summary)
        self.assertFalse(order.cost_source_worst)
