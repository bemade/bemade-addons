# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: warn when the vendor price expires before the line is delivered.

ACCEPTANCE CRITERIA
1. With a commitment date after the price list's end date, the reason ends
   with "Warning. Vendor price expires {date}, before this line's delivery
   date of {date}." and the line stays Firm.
2. Without a commitment date, the order's expected date is used.
3. A price list covering the delivery date gives no warning.
4. The warning is in the tooltip payload's warnings.
"""
from odoo.tests import tagged

from .common import SaleCostSourceCommon


@tagged("post_install", "-at_install")
class TestDeliveryWarning(SaleCostSourceCommon):
    def setUp(self):
        super().setUp()
        self.end = self._ahead(days=7)
        self._seller(date_end=self.end)

    def test_commitment_date_after_expiry_warns(self):
        delivery = self._ahead(months=2)
        line = self._line(commitment_date=delivery)
        level, reason = self._read(line)
        self.assertEqual(level, "firm")
        warning = (
            f"Warning. Vendor price expires {self._fmt(self.end)}, before this "
            f"line's delivery date of {self._fmt(delivery)}."
        )
        self.assertTrue(reason.endswith(warning), reason)
        self.assertEqual(line.cost_source_explanation["warnings"], [warning])

    def test_expected_date_is_the_fallback(self):
        self.product.sale_delay = 30
        line = self._line()
        self.assertFalse(line.order_id.commitment_date)
        self.assertIn("Warning.", self._read(line)[1])

    def test_covered_delivery_does_not_warn(self):
        line = self._line(commitment_date=self._ahead(days=2))
        self.assertNotIn("Warning.", self._read(line)[1])
