"""Use case: who can see and manage customer codes.

Acceptance criteria
-------------------
1. An internal user without sales rights can read codes but not create, edit or
   delete them.
2. A salesperson can create, edit and delete codes.
3. The *Customer Product Codes* menu is visible to the manager group only.
4. A code on a shared product is visible in every company; a code on a product
   restricted to a company is not visible to a user outside that company.
"""

from .common import CustomerProductCodeCase


class TestSecurity(CustomerProductCodeCase):
    def test_internal_user_read_only(self):
        """AC1"""

    def test_salesman_can_manage(self):
        """AC2"""

    def test_menu_restricted_to_manager_group(self):
        """AC3"""

    def test_multi_company_rule(self):
        """AC4"""
