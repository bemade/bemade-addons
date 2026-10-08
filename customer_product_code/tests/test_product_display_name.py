"""Use case: products are shown by the customer's code and name when the
customer is known.

Acceptance criteria
-------------------
1. With ``partner_id`` of a customer with a code in context, a product displays
   as ``[CUST-1] Customer Widget``.
2. With ``display_default_code=False`` in context, it displays as ``Customer
   Widget``.
3. A contact of the customer in context gives the customer's code.
4. Without a partner in context, or with a partner without a code, the standard
   Odoo display name is kept (including vendor codes from standard Odoo).
5. With ``sale_order_mode`` in context, the standard display name is kept.
6. ``partner_ref`` shows ``[CUST-1] Customer Widget`` for the customer, and the
   standard value otherwise.
7. A multi-product recordset mixes customer names and standard names correctly.
"""

from odoo import Command

from .common import CustomerProductCodeCase


class TestProductDisplayName(CustomerProductCodeCase):
    def _for(self, partner, product=None, **ctx):
        return (product or self.product).with_context(partner_id=partner.id, **ctx)

    def test_partner_context_shows_customer_code(self):
        """AC1"""
        self.assertEqual(
            self._for(self.customer).display_name, "[CUST-1] Customer Widget"
        )

    def test_variant_attributes_appended(self):
        """AC1: a variant keeps its attribute values after the customer name."""
        attribute = self.env["product.attribute"].create(
            {
                "name": "Colour",
                "value_ids": [
                    Command.create({"name": "Red"}),
                    Command.create({"name": "Blue"}),
                ],
            }
        )
        template = self.env["product.template"].create(
            {
                "name": "Paint",
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [Command.set(attribute.value_ids.ids)],
                        }
                    )
                ],
            }
        )
        red = template.product_variant_ids.filtered(
            lambda p: p.product_template_attribute_value_ids.name == "Red"
        )
        self.assertEqual(len(red), 1)
        self._add_code(self.customer, red, "PNT-1", "Customer Paint")
        self.assertEqual(
            self._for(self.customer, red).display_name,
            "[PNT-1] Customer Paint (Red)",
        )

    def test_formatted_display_name(self):
        """AC1: the formatted variant used by many2one widgets."""
        product = self._for(self.customer, formatted_display_name=True)
        self.assertEqual(product.display_name, "Customer Widget\t--CUST-1--")

    def test_display_default_code_false_hides_code(self):
        """AC2"""
        product = self._for(self.customer, display_default_code=False)
        self.assertEqual(product.display_name, "Customer Widget")

    def test_contact_context_uses_company_code(self):
        """AC3"""
        self.assertEqual(
            self._for(self.contact).display_name, "[CUST-1] Customer Widget"
        )

    def test_no_partner_or_no_code_keeps_standard_name(self):
        """AC4"""
        self.assertEqual(self.product.display_name, "[INT-1] Widget")
        vendor = self.env["res.partner"].create({"name": "Vendor"})
        self.assertEqual(self._for(vendor).display_name, "[INT-1] Widget")
        self.env["product.supplierinfo"].create(
            {
                "partner_id": vendor.id,
                "product_tmpl_id": self.template.id,
                "product_code": "VEND-1",
                "product_name": "Vendor Widget",
            }
        )
        self.product.invalidate_recordset()
        self.assertEqual(self._for(vendor).display_name, "[VEND-1] Vendor Widget")

    def test_sale_order_mode_keeps_standard_name(self):
        """AC5"""
        product = self._for(self.customer, sale_order_mode=True)
        self.assertEqual(product.display_name, "[INT-1] Widget")

    def test_partner_ref(self):
        """AC6"""
        self.assertEqual(
            self._for(self.customer).partner_ref, "[CUST-1] Customer Widget"
        )
        stranger = self.env["res.partner"].create({"name": "Stranger"})
        self.assertEqual(self._for(stranger).partner_ref, "[INT-1] Widget")

    def test_mixed_recordset(self):
        """AC7"""
        plain = self._create_product("Gadget", "INT-9")
        products = (self.product | plain).with_context(partner_id=self.customer.id)
        self.assertEqual(
            products.mapped("display_name"),
            ["[CUST-1] Customer Widget", "[INT-9] Gadget"],
        )
