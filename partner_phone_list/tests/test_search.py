# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: finding a contact by any of its numbers.

Acceptance criteria:
- Searching phone_mobile_search (the contact search "Phone" filter, caller ID)
  finds a contact by a number that is not its primary one, typed in another
  format, in full or in part.
- The primary number is still found as before.
"""

from odoo.fields import Command
from odoo.tests import tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestSearch(PhoneListCase):
    def test_search_non_primary_number(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "fax", "number": "514-555-0177", "sequence": 2}),
            ]
        )
        for term in ("+1 514 555 0177", "5145550177", "555-0177", "514-555-0101"):
            found = self.Partner.search([("phone_mobile_search", "ilike", term)])
            self.assertIn(partner, found, term)
        found = self.Partner.search([("phone_mobile_search", "=", "+15145550177")])
        self.assertIn(partner, found)
        self.assertNotIn(
            partner, self.Partner.search([("phone_mobile_search", "ilike", "5145550188")])
        )
