# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: the number list in the browser.

Acceptance criteria:
- On the contact form a user adds two numbers in the inline list, saves,
  drags the second one to the top and saves again: the dragged number becomes
  the contact's Phone.
"""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPartnerPhoneListTour(HttpCase):
    def test_partner_phone_list_tour(self):
        self.start_tour(
            "/odoo/action-base.action_partner_form/new",
            "partner_phone_list_tour",
            login="admin",
        )
        partner = self.env["res.partner"].search([("name", "=", "Sample Tour Contact")])
        self.assertEqual(len(partner.phone_ids), 2)
        self.assertIn("0222", partner.phone)
        self.assertEqual(partner.mobile, partner.phone)
