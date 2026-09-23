"""Use case: find a product by the customer's code or name.

Acceptance criteria
-------------------
1. Without a partner in context, a product is found by its internal reference
   and by any customer's code or name.
2. With a customer in context, the product is found by that customer's code and
   name, and by the standard fields.
3. With a customer in context, another customer's code does not find the product.
4. A contact of the customer in context finds by the customer's code.
5. Archived codes do not match.
6. Negative operators (``!=``, ``not ilike``) exclude products whose standard
   fields or customer code match.
7. Searching the product and product-variant search views by *Customer Product
   Code* filters on customer codes.
8. The same searches work on product templates (the sales order line's
   *Product* field) and through the dropdown search (``name_search``).
"""

from .common import CustomerProductCodeCase


class TestProductSearch(CustomerProductCodeCase):
    def _find(self, value, partner=None, operator="ilike", model="product.product"):
        records = self.env[model]
        if partner:
            records = records.with_context(partner_id=partner.id)
        return records.search([("display_name", operator, value)])

    def test_search_without_partner(self):
        """AC1"""
        for value in ("INT-1", "CUST-1", "Customer Widget", "OTHER-1"):
            self.assertIn(self.product, self._find(value), value)

    def test_search_with_customer(self):
        """AC2"""
        for value in ("INT-1", "Widget", "CUST-1", "Customer Widget"):
            self.assertIn(self.product, self._find(value, self.customer), value)

    def test_other_customer_code_not_matched(self):
        """AC3"""
        self.assertNotIn(self.product, self._find("OTHER-1", self.customer))

    def test_contact_finds_company_code(self):
        """AC4"""
        self.assertIn(self.product, self._find("CUST-1", self.contact))

    def test_archived_code_not_matched(self):
        """AC5"""
        self.code.active = False
        self.assertNotIn(self.product, self._find("CUST-1"))
        self.assertNotIn(self.product, self._find("CUST-1", self.customer))

    def test_negative_operators(self):
        """AC6"""
        self.assertNotIn(self.product, self._find("CUST-1", operator="not ilike"))
        self.assertNotIn(
            self.product, self._find("CUST-1", self.customer, operator="not ilike")
        )
        self.assertNotIn(self.product, self._find("CUST-1", operator="!="))
        self.assertIn(self.product, self._find("NOPE", operator="not ilike"))

    def test_search_by_customer_code_field(self):
        """AC7"""
        for model in ("product.product", "product.template"):
            arch = self.env[model].get_view(view_type="search")["arch"]
            self.assertIn('name="product_customer_code_ids"', arch, model)
        Product = self.env["product.product"]
        self.assertIn(
            self.product,
            Product.search([("product_customer_code_ids.product_code", "ilike", "CUST")]),
        )

    def test_template_and_name_search(self):
        """AC8"""
        self.assertIn(
            self.template,
            self._find("CUST-1", self.customer, model="product.template"),
        )
        Product = self.env["product.product"].with_context(partner_id=self.customer.id)
        self.assertIn(self.product.id, [r[0] for r in Product.name_search("Customer Wid")])
        self.assertNotIn(self.product.id, [r[0] for r in Product.name_search("OTHER-1")])
        self.assertIn(
            self.product.id,
            [r[0] for r in self.env["product.product"].name_search("OTHER-1")],
        )
        # A standard match is still returned first and not duplicated.
        ids = [r[0] for r in Product.name_search("INT-1")]
        self.assertEqual(ids.count(self.product.id), 1)
        # Once the limit is reached by standard matches, codes are not searched.
        twin = self._create_product("Customer Widget Twin", "TWIN-1")
        self.assertEqual(
            [r[0] for r in Product.name_search("Customer Widget", limit=1)],
            [twin.id],
        )
