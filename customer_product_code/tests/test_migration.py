"""Use case: upgrading a database from the commercial module.

Acceptance criteria
-------------------
1. The pre-migration aligns each code's company with its product's company.
2. If a customer has several codes on the same product, the upgrade stops with
   an error naming the customer/product pairs to fix, and changes nothing.
3. A database with no conflicting data upgrades without error.
"""

from .common import CustomerProductCodeCase


class TestMigration(CustomerProductCodeCase):
    def test_company_aligned_with_product(self):
        """AC1"""

    def test_duplicates_abort_upgrade(self):
        """AC2"""

    def test_clean_database_upgrades(self):
        """AC3"""
