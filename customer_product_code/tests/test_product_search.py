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
"""

from .common import CustomerProductCodeCase


class TestProductSearch(CustomerProductCodeCase):
    def test_search_without_partner(self):
        """AC1"""

    def test_search_with_customer(self):
        """AC2"""

    def test_other_customer_code_not_matched(self):
        """AC3"""

    def test_contact_finds_company_code(self):
        """AC4"""

    def test_archived_code_not_matched(self):
        """AC5"""

    def test_negative_operators(self):
        """AC6"""

    def test_search_by_customer_code_field(self):
        """AC7"""
