"""Use case: product templates are listed by internal reference.

Acceptance criteria
-------------------
1. Product templates are ordered by internal reference, then name.
2. A template's internal reference reflects its first variant's internal
   reference, and is searchable and sortable.
"""

from .common import CustomerProductCodeCase


class TestProductTemplateList(CustomerProductCodeCase):
    def test_template_order(self):
        """AC1"""

    def test_template_default_code_from_variant(self):
        """AC2"""
