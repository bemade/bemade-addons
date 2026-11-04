"""Use case: the forms users work in load and behave.

Acceptance criteria
-------------------
1. Customer codes can be added from the product form's *Customer Codes* tab.
2. The customer code form creates a code.
3. On a customer invoice, invoice lines display the product by the customer's
   code and name; vendor bills keep the standard behaviour.
4. On a delivery to the customer, moves display the product by the customer's
   code and name; receipts keep the standard behaviour.
"""

from lxml import etree

from odoo.tests import Form
from odoo.tools.safe_eval import safe_eval

from .common import CustomerProductCodeCase


class TestViews(CustomerProductCodeCase):
    def _field_context(self, model, xpath, values):
        """Evaluate the context a view gives a product field."""
        arch = etree.fromstring(self.env[model].get_view(view_type="form")["arch"])
        (node,) = arch.xpath(xpath)
        return safe_eval(node.get("context", "{}"), values)

    def test_product_form_customer_codes_tab(self):
        """AC1"""
        with Form(self.env["product.template"]) as form:
            form.name = "Sprocket"
            with form.product_customer_code_ids.new() as line:
                line.partner_id = self.customer
                line.product_code = "SPR-1"
                line.product_name = "Customer Sprocket"
        code = form.record.product_customer_code_ids
        self.assertEqual(
            (code.partner_id, code.product_code), (self.customer, "SPR-1")
        )

    def test_customer_code_form(self):
        """AC2"""
        other = self._create_product("Cog", "COG-1")
        with Form(self.env["product.customer.code"]) as form:
            form.partner_id = self.customer
            form.product_id = other.product_tmpl_id
            form.product_code = "COG-C"
        self.assertEqual(form.record.product_code, "COG-C")

    def test_invoice_line_display(self):
        """AC3"""
        xpath = "//field[@name='invoice_line_ids']/list/field[@name='product_id']"
        for move_type, expected in (
            ("out_invoice", "[CUST-1] Customer Widget"),
            ("in_invoice", "[INT-1] Widget"),
        ):
            parent = type("Parent", (), {})()
            parent.partner_id = self.customer.id
            parent.move_type = move_type
            ctx = self._field_context("account.move", xpath, {"parent": parent})
            product = self.product.with_context(**ctx)
            self.assertEqual(product.display_name, expected, move_type)

    def test_picking_move_display(self):
        """AC4"""
        xpath = "//field[@name='move_ids']/list/field[@name='product_id']"
        for code, expected in (
            ("outgoing", "[CUST-1] Customer Widget"),
            ("incoming", "[INT-1] Widget"),
        ):
            parent = type("Parent", (), {})()
            parent.partner_id = self.customer.id
            parent.picking_type_code = code
            ctx = self._field_context("stock.picking", xpath, {"parent": parent})
            ctx = {k: v for k, v in ctx.items() if not k.startswith("default_")}
            product = self.product.with_context(**ctx)
            self.assertEqual(product.display_name, expected, code)
