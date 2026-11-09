# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: stock with no cost value is not a firm cost.

Stock is valued at what was paid for it, so stock covering a demand is
normally firm evidence. Stock valued at zero (a standard cost never set, an
unvalued receipt) says nothing about what the goods cost: quoting from it is
quoting from a blank.

ACCEPTANCE CRITERIA
1. Stock with a real valuation covering the demand stays Firm, with no warning.
2. Stock valued at zero covering the demand resolves as Unknown, with a
   warning that the stock has no cost value and the cost shown is not reliable.
3. When other evidence exists (a vendor price), it is cited as the likely
   cost, but the line stays Unknown and keeps the warning.
4. Zero-valued stock covering only part of the demand still makes the whole
   resolution Unknown, whatever prices the rest.
"""
from odoo.tests import tagged

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestZeroValuedStock(ProductCostSourceCommon):
    def test_valued_stock_stays_firm(self):
        self._set_stock_value(10.0)
        resolution = self._resolve(qty=5, qty_from_stock=5)
        self.assertEqual(resolution.confidence, "firm")
        self.assertEqual(resolution.warnings, [])

    def test_zero_valued_stock_is_unknown_and_warned(self):
        self._set_stock_value(0.0)
        resolution = self._resolve(qty=5, qty_from_stock=5)
        self.assertEqual(resolution.confidence, "unknown")
        self.assertEqual(len(resolution.warnings), 1)
        self.assertIn("Stock has no cost value", resolution.warnings[0])
        self.assertIn(self._money(0.0), resolution.warnings[0])
        self.assertTrue(resolution.evidence[0].startswith("Unknown."))

    def test_other_evidence_cited_as_likely_cost(self):
        self._set_stock_value(0.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=5, qty_from_stock=5)
        self.assertEqual(resolution.confidence, "unknown")
        self.assertTrue(resolution.warnings)
        likely = [s for s in resolution.evidence if s.startswith("Likely cost")]
        self.assertEqual(len(likely), 1)
        self.assertIn(self._money(15.0), likely[0])

    def test_partial_zero_valued_stock_is_unknown(self):
        self._set_stock_value(0.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=10, qty_from_stock=4)
        self.assertEqual(resolution.confidence, "unknown")
        self.assertTrue(resolution.warnings)
        # the vendor price is already cited for the balance: not repeated
        self.assertFalse(
            [s for s in resolution.evidence if s.startswith("Likely cost")]
        )
