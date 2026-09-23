"""Use case: the forms users work in load and behave.

Acceptance criteria
-------------------
1. Customer codes can be added from the product form's *Customer Codes* tab.
2. The customer code form creates a code.
3. On an invoice for the customer, invoice lines display the product by the
   customer's code and name.
4. On a delivery for the customer, moves display the product by the customer's
   code and name.
"""

from .common import CustomerProductCodeCase


class TestViews(CustomerProductCodeCase):
    def test_product_form_customer_codes_tab(self):
        """AC1"""

    def test_customer_code_form(self):
        """AC2"""

    def test_invoice_line_display(self):
        """AC3"""

    def test_picking_move_display(self):
        """AC4"""
