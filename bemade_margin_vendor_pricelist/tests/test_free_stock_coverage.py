"""Use case: the margin counts only the free stock of the order's warehouse.

The margin is blended between stock cost and vendor price according to how much of
a line is covered by stock. Coverage follows one shared rule (also used by the
"cost basis" indicator of ``sale_cost_source``):

Acceptance criteria:
- On a quotation in warehouse A, stock that only exists in warehouse B is not
  counted: the margin uses the vendor price.
- Partial free stock in the order's warehouse gives a blended cost.
- Stock reserved for another order is not counted.
- On a confirmed line, the quantity already reserved on its own delivery counts as
  covered; the rest draws on the free stock.
- A line whose UoM differs from the product's UoM is computed correctly (the
  missing quantity comes back in the line's UoM).
- Two lines of the same product on the same order draw on the free stock in
  sequence (two lines of 6 against 10 in stock: 6 and 4 covered).
- Computing one line alone gives the same answer as computing the whole order.
- A negative free quantity counts as no stock.
"""

from unittest.mock import PropertyMock, patch

from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestFreeStockCoverage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.wh_a = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.wh_b = cls.env["stock.warehouse"].create(
            {"name": "Second Warehouse", "code": "WHB2", "company_id": cls.company.id}
        )
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Test Vendor", "supplier_rank": 1}
        )
        cls.customer = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.dozen = cls.env.ref("uom.product_uom_dozen")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Coverage Product",
                "type": "consu",
                "is_storable": True,
                "list_price": 100.0,
                "standard_price": 80.0,
                "uom_id": cls.unit.id,
            }
        )
        cls.env["product.supplierinfo"].create(
            {
                "partner_id": cls.vendor.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "min_qty": 1,
                "price": 60.0,
                "currency_id": cls.company.currency_id.id,
            }
        )

    # helpers -------------------------------------------------------------

    def _stock(self, warehouse, qty):
        self.env["stock.quant"]._update_available_quantity(
            self.product, warehouse.lot_stock_id, qty
        )

    def _order(self, lines, warehouse=None):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "warehouse_id": (warehouse or self.wh_a).id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": qty,
                            "price_unit": 120.0,
                            **extra,
                        },
                    )
                    for qty, extra in lines
                ],
            }
        )
        return order

    def assertBlend(self, line, qty_from_stock):
        qty = line.product_uom_qty
        expected = (
            qty_from_stock * line.purchase_price
            + (qty - qty_from_stock) * line.purchase_price_vendor
        ) / qty
        # purchase_price_actual is stored at "Product Price" digits
        self.assertAlmostEqual(line.purchase_price_actual, expected, places=2)

    # quotations ------------------------------------------------------------

    def test_stock_in_other_warehouse_not_counted(self):
        self._stock(self.wh_b, 50)
        line = self._order([(10, {})]).order_line
        self.assertAlmostEqual(line._determine_missing_stock(), 10)
        self.assertAlmostEqual(line.purchase_price_actual, line.purchase_price_vendor)
        self.assertNotAlmostEqual(line.purchase_price_actual, line.purchase_price)

    def test_partial_free_stock_blends(self):
        self._stock(self.wh_a, 4)
        self._stock(self.wh_b, 50)
        line = self._order([(10, {})]).order_line
        self.assertAlmostEqual(line._determine_missing_stock(), 6)
        self.assertBlend(line, 4)

    def test_reserved_for_other_order_not_counted(self):
        self._stock(self.wh_a, 10)
        other = self._order([(8, {})])
        other.action_confirm()
        self.assertAlmostEqual(other.order_line.move_ids.quantity, 8)
        line = self._order([(10, {})]).order_line
        self.assertAlmostEqual(line._determine_missing_stock(), 8)
        self.assertBlend(line, 2)

    def test_line_uom_differs_from_product_uom(self):
        self._stock(self.wh_a, 18)
        line = self._order([(2, {"product_uom_id": self.dozen.id})]).order_line
        self.assertEqual(line.product_uom_id, self.dozen)
        # 18 units = 1.5 dozen covered, 0.5 dozen missing (in the line's UoM)
        self.assertAlmostEqual(line._determine_missing_stock(), 0.5)
        self.assertBlend(line, 1.5)

    def test_line_uom_differs_fully_covered(self):
        self._stock(self.wh_a, 24)
        line = self._order([(2, {"product_uom_id": self.dozen.id})]).order_line
        self.assertAlmostEqual(line._determine_missing_stock(), 0)
        self.assertAlmostEqual(line.purchase_price_actual, line.purchase_price)

    def test_same_product_lines_draw_in_sequence(self):
        self._stock(self.wh_a, 10)
        order = self._order([(6, {}), (6, {})])
        first, second = order.order_line.sorted(lambda l: (l.sequence, l.id))
        self.assertAlmostEqual(first._determine_missing_stock(), 0)
        self.assertAlmostEqual(second._determine_missing_stock(), 2)
        self.assertAlmostEqual(first.purchase_price_actual, first.purchase_price)
        self.assertBlend(second, 4)

    def test_single_line_matches_whole_order(self):
        self._stock(self.wh_a, 10)
        order = self._order([(6, {}), (6, {})])
        second = order.order_line.sorted(lambda l: (l.sequence, l.id))[1]
        self.env.invalidate_all()
        # read the second line alone first: it must still see the first line's draw
        self.assertBlend(second, 4)

    def test_negative_free_qty_counts_as_zero(self):
        line = self._order([(10, {})]).order_line
        with patch.object(
            self.product.__class__,
            "free_qty",
            new_callable=PropertyMock,
            return_value=-5,
        ):
            self.assertAlmostEqual(line._determine_missing_stock(), 10)

    # confirmed orders ------------------------------------------------------

    def test_confirmed_own_reservation_counts(self):
        self._stock(self.wh_a, 10)
        order = self._order([(10, {})])
        order.action_confirm()
        line = order.order_line
        self.assertAlmostEqual(line.move_ids.quantity, 10)
        # free_qty is now 0, but the line's own reservation covers it
        self.assertAlmostEqual(line._determine_missing_stock(), 0)
        self.assertAlmostEqual(line.purchase_price_actual, line.purchase_price)

    def test_confirmed_partial_reservation(self):
        self._stock(self.wh_a, 4)
        order = self._order([(10, {})])
        order.action_confirm()
        line = order.order_line
        self.assertAlmostEqual(line.move_ids.quantity, 4)
        self.assertAlmostEqual(line._determine_missing_stock(), 6)
        self.assertBlend(line, 4)

    def test_confirmed_unreserved_uses_free_stock(self):
        order = self._order([(10, {})])
        order.action_confirm()
        line = order.order_line
        self.assertAlmostEqual(line.move_ids.quantity, 0)
        # stock arrives after confirmation, not yet reserved
        self._stock(self.wh_a, 7)
        self.assertAlmostEqual(line._determine_missing_stock(), 3)

    def test_confirmed_other_warehouse_stock_not_counted(self):
        self._stock(self.wh_b, 50)
        order = self._order([(10, {})])
        order.action_confirm()
        self.assertAlmostEqual(order.order_line._determine_missing_stock(), 10)
