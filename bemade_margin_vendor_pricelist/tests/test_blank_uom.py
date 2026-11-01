"""Use case: a user clears the unit of measure on a sales order line (task 4720).

Acceptance criteria:
- Clearing the UoM on a quotation line and tabbing out (onchange) raises no error;
  the margin fields are still computed.
- With the UoM blank, ``purchase_price_actual`` equals the value computed for the same
  line with its UoM set (vendor-price case: nothing in stock), and ``gross_profit`` is
  ``price_subtotal - purchase_price_actual * qty`` (core resets the unit price when the
  UoM is cleared, so the subtotal itself may change).
"""

from unittest.mock import PropertyMock, patch

from odoo.tests import Form, TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestBlankUom(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # the UoM column is only shown (and editable) with the UoM group
        cls.env.user.group_ids += cls.env.ref("uom.group_uom")
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Test Vendor", "supplier_rank": 1}
        )
        cls.customer = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "is_storable": True,
                "list_price": 100.0,
                "standard_price": 80.0,
            }
        )
        cls.env["product.supplierinfo"].create(
            {
                "partner_id": cls.vendor.id,
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "min_qty": 1,
                "price": 75.0,
            }
        )
        cls.sale_order = cls.env["sale.order"].create({"partner_id": cls.customer.id})
        cls.line = cls.env["sale.order.line"].create(
            {
                "order_id": cls.sale_order.id,
                "product_id": cls.product.id,
                "product_uom_qty": 10,
                "price_unit": 120.0,
            }
        )

    def _patch_qty_available(self, qty):
        return patch.object(
            self.product.__class__,
            "qty_available",
            new_callable=PropertyMock,
            return_value=qty,
        )

    def test_blank_uom_compute_no_error(self):
        """Computing margins on a line with no UoM gives the vendor-price values."""
        with self._patch_qty_available(0):
            expected_actual = self.line.purchase_price_actual
            self.assertEqual(expected_actual, self.line.purchase_price_vendor)
            self.line.product_uom_id = False
            self.line._compute_actual_gp()
            self.assertAlmostEqual(self.line.purchase_price_actual, expected_actual)
            self.assertAlmostEqual(
                self.line.gross_profit,
                self.line.price_subtotal
                - expected_actual * self.line.product_uom_qty,
            )

    def test_blank_uom_onchange_no_error(self):
        """Clearing the UoM in the form (onchange) raises no error."""
        with self._patch_qty_available(0):
            order_form = Form(self.sale_order)
            with order_form.order_line.edit(0) as line_form:
                expected_actual = line_form.purchase_price_actual
                line_form.product_uom_id = self.env["uom.uom"]
                self.assertAlmostEqual(
                    line_form.purchase_price_actual, expected_actual
                )
                # restore so the form can be saved (UoM is required in the view)
                line_form.product_uom_id = self.product.uom_id
