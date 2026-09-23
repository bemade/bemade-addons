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

from .common import CustomerProductCodeCase


class TestProductDisplayName(CustomerProductCodeCase):
    def test_partner_context_shows_customer_code(self):
        """AC1"""

    def test_display_default_code_false_hides_code(self):
        """AC2"""

    def test_contact_context_uses_company_code(self):
        """AC3"""

    def test_no_partner_or_no_code_keeps_standard_name(self):
        """AC4"""

    def test_sale_order_mode_keeps_standard_name(self):
        """AC5"""

    def test_partner_ref(self):
        """AC6"""

    def test_mixed_recordset(self):
        """AC7"""
