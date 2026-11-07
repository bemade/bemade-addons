"""A replenishment line without a vendor finds its own.

Acceptance criteria:

- A manual line with no vendor gets one as soon as its product has a vendor
  price, even when that price is added after the line was created.
- A line switched from automatic to manual gets one too.
- An automatic line is left empty: Odoo chooses the vendor when it orders.
- A vendor already on the line, chosen by hand or filled earlier, is never
  replaced when the product's prices change.
- If the price the line points to is deleted, the line finds the next one.
- The first current price wins, by sequence; expired prices only count when
  the product has nothing else. A price restricted to another company is
  never used.
- Existing empty lines are filled by the upgrade.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import ReplenishVendorCase


@tagged("-at_install", "post_install")
class TestVendorFill(ReplenishVendorCase):
    def test_price_added_after_line(self):
        line = self._make_line()
        self.assertFalse(line.supplier_id)
        price = self._add_price(self.vendor1)
        self.assertEqual(line.supplier_id, price)
        self.assertEqual(line.vendor_id, self.vendor1)

    def test_switch_auto_to_manual(self):
        price = self._add_price(self.vendor1)
        line = self._make_line(trigger="auto")
        self.assertFalse(line.supplier_id)
        line.trigger = "manual"
        self.assertEqual(line.supplier_id, price)

    def test_auto_line_stays_empty(self):
        line = self._make_line(trigger="auto")
        self._add_price(self.vendor1)
        self.assertFalse(line.supplier_id)

    def test_hand_choice_kept_when_prices_change(self):
        self._add_price(self.vendor1, sequence=5)
        chosen = self._add_price(self.vendor2, sequence=10)
        line = self._make_line()
        line.supplier_id = chosen
        self._add_price(self.vendor1, sequence=1, min_qty=30)
        self.assertEqual(line.supplier_id, chosen)

    def test_filled_vendor_kept_when_prices_change(self):
        first = self._add_price(self.vendor1, sequence=5)
        line = self._make_line()
        self.assertEqual(line.supplier_id, first)
        self._add_price(self.vendor2, sequence=1)
        self.assertEqual(line.supplier_id, first)

    def test_deleted_price_refills(self):
        first = self._add_price(self.vendor1, sequence=1)
        second = self._add_price(self.vendor2, sequence=2)
        line = self._make_line()
        self.assertEqual(line.supplier_id, first)
        first.unlink()
        self.assertEqual(line.supplier_id, second)

    def test_expired_price_skipped(self):
        yesterday = fields.Date.today() - timedelta(days=1)
        self._add_price(self.vendor1, sequence=1, date_end=yesterday)
        current = self._add_price(self.vendor2, sequence=2)
        line = self._make_line()
        self.assertEqual(line.supplier_id, current)

    def test_only_expired_prices_still_fill(self):
        yesterday = fields.Date.today() - timedelta(days=1)
        expired = self._add_price(self.vendor1, date_end=yesterday)
        line = self._make_line()
        self.assertEqual(line.supplier_id, expired)

    def test_other_company_price_ignored(self):
        other = self.env["res.company"].create({"name": "Other Co"})
        self._add_price(self.vendor1, sequence=1, company_id=other.id)
        mine = self._add_price(self.vendor2, sequence=2)
        line = self._make_line()
        self.assertEqual(line.supplier_id, mine)

    def test_upgrade_fills_existing_empty_lines(self):
        other = self.env["product.product"].create(
            {"name": "Fitting", "is_storable": True}
        )
        line = self._make_line()
        auto = self._make_line(product=other, trigger="auto")
        self.env.flush_all()
        # Lines left empty by the old code: the price came later, and nothing
        # recomputed them.
        self._add_price(self.vendor1)
        self._add_price(self.vendor1, product=other)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE stock_warehouse_orderpoint SET supplier_id = NULL, "
            "vendor_id = NULL WHERE id IN %s",
            (tuple((line | auto).ids),),
        )
        self.env.invalidate_all()
        self.assertFalse(line.supplier_id)

        self.env["stock.warehouse.orderpoint"]._fill_missing_supplier()

        self.assertEqual(line.supplier_id.partner_id, self.vendor1)
        self.assertEqual(line.vendor_id, self.vendor1)
        self.assertFalse(auto.supplier_id)
