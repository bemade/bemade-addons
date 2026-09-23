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

from .common import CustomerProductCodeCase


class TestSaleOrderLineDescription(CustomerProductCodeCase):
    def test_form_line_uses_customer_code_and_sale_description(self):
        """AC1"""

    def test_api_line_uses_customer_code(self):
        """AC2"""

    def test_no_sale_description(self):
        """AC3"""

    def test_contact_and_address_use_company_code(self):
        """AC4"""

    def test_blank_code_or_name_falls_back_to_product(self):
        """AC5"""

    def test_customer_without_code_gets_standard_description(self):
        """AC6"""

    def test_section_and_note_lines_unaffected(self):
        """AC7"""

    def test_order_line_product_keeps_standard_name(self):
        """AC8"""
