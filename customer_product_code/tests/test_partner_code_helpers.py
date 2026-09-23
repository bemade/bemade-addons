"""Use case: other modules query a product's code for a customer.

These methods are a public contract: dependent modules call them.

Acceptance criteria
-------------------
1. ``has_customer_code(partner)`` is true when the product has an active code for
   the partner or its commercial partner, false otherwise.
2. ``_get_partner_code_name(product, partner)`` returns ``{"code", "name"}`` from
   the partner's (or commercial partner's) code, falling back per field to the
   product's internal reference and name.
3. Without a partner, or without a code, it returns the product's internal
   reference and name.
"""

from .common import CustomerProductCodeCase


class TestPartnerCodeHelpers(CustomerProductCodeCase):
    def test_has_customer_code(self):
        """AC1"""
        stranger = self.env["res.partner"].create({"name": "Stranger"})
        self.assertTrue(self.product.has_customer_code(self.customer))
        self.assertTrue(self.product.has_customer_code(self.contact))
        self.assertFalse(self.product.has_customer_code(stranger))
        self.code.active = False
        self.assertFalse(self.product.has_customer_code(self.customer))

    def test_get_partner_code_name(self):
        """AC2"""
        product = self.product
        self.assertEqual(
            product._get_partner_code_name(product, self.contact),
            {"code": "CUST-1", "name": "Customer Widget"},
        )
        self.code.product_code = False
        self.assertEqual(
            product._get_partner_code_name(product, self.customer),
            {"code": "INT-1", "name": "Customer Widget"},
        )

    def test_get_partner_code_name_fallback(self):
        """AC3"""
        stranger = self.env["res.partner"].create({"name": "Stranger"})
        expected = {"code": "INT-1", "name": "Widget"}
        product = self.product
        self.assertEqual(product._get_partner_code_name(product, stranger), expected)
        self.assertEqual(
            product._get_partner_code_name(product, self.env["res.partner"]),
            expected,
        )
