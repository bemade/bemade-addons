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

from .common import CustomerProductCodeCase


class TestCustomerCodeModel(CustomerProductCodeCase):
    def test_company_follows_product(self):
        """AC1"""

    def test_duplicate_customer_product_refused(self):
        """AC2"""

    def test_other_customer_same_product_allowed(self):
        """AC3"""

    def test_same_code_on_several_products_allowed(self):
        """AC4"""

    def test_display_name_is_code(self):
        """AC5"""

    def test_archived_code_hidden(self):
        """AC6"""

    def test_copy_product_does_not_copy_codes(self):
        """AC7"""
