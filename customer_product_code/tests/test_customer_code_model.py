"""Use case: record a customer's own code and name for a product.

Acceptance criteria
-------------------
1. A code links a customer and a product template to the customer's code and
   name; its company is the product's company (none for a shared product) and
   follows the product when the product's company changes.
2. A second code for the same customer and product is refused.
3. Another customer may have a code on the same product.
4. The same code value may be used by one customer on several products.
5. A code record is displayed by its code value.
6. Archiving a code hides it from searches and from the product's codes.
7. Duplicating a product does not duplicate its customer codes.
"""

from psycopg2 import IntegrityError

from odoo.tools.misc import mute_logger

from .common import CustomerProductCodeCase


class TestCustomerCodeModel(CustomerProductCodeCase):
    def test_company_follows_product(self):
        """AC1"""
        self.assertFalse(self.code.company_id)
        self.template.company_id = self.env.company
        self.assertEqual(self.code.company_id, self.env.company)
        self.template.company_id = False
        self.assertFalse(self.code.company_id)

    def test_company_given_on_create_is_ignored(self):
        """AC1: importers passing a company get the product's company."""
        third = self.env["res.partner"].create({"name": "Initech"})
        code = self.env["product.customer.code"].create(
            {
                "partner_id": third.id,
                "product_id": self.template.id,
                "product_code": "INI-1",
                "company_id": self.env.company.id,
            }
        )
        self.assertFalse(code.company_id)

    def test_duplicate_customer_product_refused(self):
        """AC2"""
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self._add_code(self.customer, self.product, "CUST-2")

    def test_other_customer_same_product_allowed(self):
        """AC3"""
        third = self.env["res.partner"].create({"name": "Initech"})
        code = self._add_code(third, self.product, "INI-1")
        self.assertEqual(
            self.template.product_customer_code_ids,
            self.code | self.other_code | code,
        )

    def test_same_code_on_several_products_allowed(self):
        """AC4"""
        equivalent = self._create_product("Equivalent Widget", "INT-2")
        code = self._add_code(self.customer, equivalent, "CUST-1")
        self.assertEqual(code.product_code, self.code.product_code)

    def test_display_name_is_code(self):
        """AC5"""
        self.assertEqual(self.code.display_name, "CUST-1")

    def test_archived_code_hidden(self):
        """AC6"""
        self.code.active = False
        Code = self.env["product.customer.code"]
        self.assertFalse(Code.search([("product_code", "=", "CUST-1")]))
        self.template.invalidate_recordset(["product_customer_code_ids"])
        self.assertEqual(self.template.product_customer_code_ids, self.other_code)

    def test_copy_product_does_not_copy_codes(self):
        """AC7"""
        self.assertFalse(self.template.copy().product_customer_code_ids)
        self.assertFalse(
            self.product.copy().product_tmpl_id.product_customer_code_ids
        )
