# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: the phonebook dialog in the browser.

Acceptance criteria:
- On a new contact, the phonebook button of the Phone row opens a dialog with
  the number list; adding two numbers there and closing it with Done shows
  the top number (formatted) as Phone and the mobile as Mobile on the form,
  before saving.
- On a saved contact, dragging a number to the top in the dialog and clicking
  Save saves the contact: the dragged number becomes the Phone.
- In the child-contact popup the same dialog opens on top of the popup (a new
  child contact); its numbers are saved with the popup.
"""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPartnerPhoneListTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.country_id = cls.env.ref("base.ca")
        cls.env.ref("base.user_admin").partner_id.country_id = cls.env.ref("base.ca")

    def test_partner_phone_list_tour(self):
        self.start_tour(
            "/odoo/action-base.action_partner_form/new",
            "partner_phone_list_tour",
            login="admin",
        )
        partner = self.env["res.partner"].search([("name", "=", "Sample Tour Contact")])
        self.assertEqual(len(partner.phone_ids), 2)
        self.assertEqual(partner.phone, "+1 514-555-0222")
        self.assertEqual(partner.mobile, partner.phone)

    def test_partner_phone_list_child_tour(self):
        self.start_tour(
            "/odoo/action-base.action_partner_form/new",
            "partner_phone_list_child_tour",
            login="admin",
        )
        company = self.env["res.partner"].search([("name", "=", "Sample Tour Company")])
        child = company.child_ids
        self.assertEqual(child.name, "Sample Tour Child")
        self.assertEqual(child.phone_ids.type, "mobile")
        self.assertEqual(child.mobile, "+1 438-555-0133")
