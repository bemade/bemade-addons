"""Use case: a sales order line describes the product in the customer's terms.

Acceptance criteria
-------------------
1. Adding a product to an order for a customer with a code, through the order
   form, sets the line description to ``[CUST-1] Customer Widget`` followed by
   the product's sales description on a new line.
2. The same holds when the line is created through the API.
3. Without a sales description, the description is only ``[CUST-1] Customer
   Widget``.
4. An order for a contact or delivery address of the customer uses the
   customer's (commercial partner's) code.
5. If the code or the name is blank on the customer code, the product's internal
   reference or name is used in its place.
6. An order for a customer without a code gets the standard Odoo description.
7. Section and note lines (no product) are unaffected.
8. On the order line, the product field itself keeps the standard product name.
"""

from odoo.tests import Form

from .common import CustomerProductCodeCase

EXPECTED = "[CUST-1] Customer Widget\nSales blurb"


class TestSaleOrderLineDescription(CustomerProductCodeCase):
    def _order_line(self, partner, product=None, **vals):
        order = self.env["sale.order"].create({"partner_id": partner.id})
        return self.env["sale.order.line"].create(
            {"order_id": order.id, "product_id": (product or self.product).id, **vals}
        )

    def test_form_line_uses_customer_code_and_sale_description(self):
        """AC1"""
        with Form(self.env["sale.order"]) as order_form:
            order_form.partner_id = self.customer
            with order_form.order_line.new() as line:
                line.product_id = self.product
        self.assertEqual(order_form.record.order_line.name, EXPECTED)

    def test_api_line_uses_customer_code(self):
        """AC2"""
        self.assertEqual(self._order_line(self.customer).name, EXPECTED)

    def test_no_sale_description(self):
        """AC3"""
        self.product.description_sale = False
        self.assertEqual(
            self._order_line(self.customer).name, "[CUST-1] Customer Widget"
        )

    def test_contact_and_address_use_company_code(self):
        """AC4"""
        self.assertEqual(self._order_line(self.contact).name, EXPECTED)
        self.assertEqual(self._order_line(self.delivery_address).name, EXPECTED)

    def test_contact_own_code_takes_precedence(self):
        """AC4: a code recorded on the contact itself wins over the company's."""
        self._add_code(self.contact, self.product, "JANE-1", "Jane Widget")
        self.assertEqual(
            self._order_line(self.contact).name, "[JANE-1] Jane Widget\nSales blurb"
        )

    def test_blank_code_or_name_falls_back_to_product(self):
        """AC5"""
        self.code.product_name = False
        self.assertEqual(
            self._order_line(self.customer).name, "[CUST-1] Widget\nSales blurb"
        )
        self.code.write({"product_name": "Customer Widget", "product_code": False})
        self.assertEqual(
            self._order_line(self.customer).name,
            "[INT-1] Customer Widget\nSales blurb",
        )

    def test_customer_without_code_gets_standard_description(self):
        """AC6"""
        stranger = self.env["res.partner"].create({"name": "Stranger"})
        self.assertEqual(
            self._order_line(stranger).name, "[INT-1] Widget\nSales blurb"
        )

    def test_customer_with_vendor_code_only_gets_standard_description(self):
        """AC6: a vendor code for the same partner does not leak into sales."""
        vendor = self.env["res.partner"].create({"name": "Vendor Too"})
        self.env["product.supplierinfo"].create(
            {
                "partner_id": vendor.id,
                "product_tmpl_id": self.template.id,
                "product_code": "VEND-1",
                "product_name": "Vendor Widget",
            }
        )
        self.assertEqual(self._order_line(vendor).name, "[INT-1] Widget\nSales blurb")

    def test_section_and_note_lines_unaffected(self):
        """AC7"""
        order = self.env["sale.order"].create({"partner_id": self.customer.id})
        section, note = self.env["sale.order.line"].create(
            [
                {"order_id": order.id, "display_type": "line_section", "name": "Sec"},
                {"order_id": order.id, "display_type": "line_note", "name": "Note"},
            ]
        )
        self.assertEqual((section.name, note.name), ("Sec", "Note"))
        self.assertFalse(
            self.env["product.product"].get_product_multiline_description_sale()
        )

    def test_order_line_product_keeps_standard_name(self):
        """AC8"""
        arch = self.env["sale.order"].get_view(view_type="form")["arch"]
        self.assertIn("sale_order_mode", arch)
        product = self.product.with_context(
            partner_id=self.customer.id, sale_order_mode=True
        )
        self.assertEqual(product.display_name, "[INT-1] Widget")
