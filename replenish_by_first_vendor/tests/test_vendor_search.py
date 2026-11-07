"""The Replenishment screen's Vendor search finds every product priced there.

Acceptance criteria:

- Searching "Vendor" for a vendor finds a line whose product has a price from
  that vendor, even when that vendor is not the product's first one and the
  line's own vendor is another.
- It works both when typing a name and when picking the vendor from the
  suggestions.
- It does not find a line whose product has no price from that vendor.

The domain tested is the one the screen's search view really uses.
"""

from lxml import etree

from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import ReplenishVendorCase


@tagged("-at_install", "post_install")
class TestVendorSearch(ReplenishVendorCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._add_price(cls.vendor1, sequence=1)
        cls._add_price(cls.vendor2, sequence=2)
        cls.other_product = cls.env["product.product"].create(
            {"name": "Fitting", "is_storable": True}
        )
        cls._add_price(cls.vendor1, product=cls.other_product)

    def setUp(self):
        super().setUp()
        self.line = self._make_line()
        self.other_line = self._make_line(product=self.other_product)
        self.assertEqual(self.line.vendor_id, self.vendor1)

    def _search_vendor(self, value):
        Orderpoint = self.env["stock.warehouse.orderpoint"]
        view = self.env.ref("stock.stock_reorder_report_search")
        arch = Orderpoint.get_views([(view.id, "search")])["views"]["search"]["arch"]
        node = etree.fromstring(arch).xpath("/search/field[@name='vendor_id']")[0]
        domain = safe_eval(node.get("filter_domain"), {"self": value})
        return Orderpoint.search(domain + [("id", "in", (self.line | self.other_line).ids)])

    def test_typed_name_finds_second_vendor(self):
        self.assertEqual(self._search_vendor("Beta Val"), self.line)

    def test_picked_vendor_finds_second_vendor(self):
        self.assertEqual(self._search_vendor(self.vendor2.id), self.line)

    def test_first_vendor_still_found(self):
        self.assertEqual(
            self._search_vendor(self.vendor1.id), self.line | self.other_line
        )
