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

    def test_get_partner_code_name(self):
        """AC2"""

    def test_get_partner_code_name_fallback(self):
        """AC3"""
