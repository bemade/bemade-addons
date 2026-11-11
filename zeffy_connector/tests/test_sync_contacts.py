# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Use case: Zeffy contacts are matched to Odoo contacts without duplicates.

Acceptance criteria
- A Zeffy contact is linked to the Odoo contact with the same email,
  case-insensitively.
- Failing that, to the Odoo contact with the same name and postal code
  (postal code compared without spaces, case-insensitively).
- Failing that, a person is created with the name, email, phone and address
  (province and country resolved from their codes).
- Matching never modifies the existing Odoo contact.
- Once linked, a Zeffy contact keeps its Odoo contact on later runs, even if
  its email changes in Zeffy.
- After a first complete pass, later runs only ask Zeffy for contacts
  updated since the previous pass.
"""

from odoo.tests import tagged

from .common import ZeffyCase, make_address, make_contact


@tagged("post_install", "-at_install")
class TestZeffySyncContacts(ZeffyCase):
    def _zeffy_contact(self, data):
        return self.Contact.search([("zeffy_id", "=", data["id"])])

    def test_match_by_email_case_insensitive(self):
        partner = self.Partner.create(
            {"name": "A. Martin", "email": "Alex.Martin@Example.com", "phone": "111"}
        )
        data = make_contact(email="alex.martin@example.com")
        self.api.contacts = [data]
        self.sync()
        contact = self._zeffy_contact(data)
        self.assertEqual(contact.partner_id, partner)
        self.assertEqual(partner.name, "A. Martin", "existing contact untouched")
        self.assertEqual(partner.phone, "111", "existing contact untouched")

    def test_match_by_name_and_postal_code(self):
        partner = self.Partner.create(
            {"name": "Sam Gagnon", "zip": "j0a1b0", "email": "other@example.com"}
        )
        data = make_contact(
            email="sam.new@example.com",
            first_name="Sam",
            last_name="Gagnon",
            address=make_address(postal_code="J0A 1B0"),
        )
        self.api.contacts = [data]
        self.sync()
        self.assertEqual(self._zeffy_contact(data).partner_id, partner)

    def test_same_name_other_postal_code_is_not_matched(self):
        partner = self.Partner.create({"name": "Sam Gagnon", "zip": "H2X 1Y4"})
        data = make_contact(
            email="sam.new@example.com", first_name="Sam", last_name="Gagnon"
        )
        self.api.contacts = [data]
        self.sync()
        self.assertNotEqual(self._zeffy_contact(data).partner_id, partner)

    def test_unmatched_contact_creates_person_with_address(self):
        data = make_contact(email="new.donor@example.com", first_name="Robin", last_name="Roy")
        self.api.contacts = [data]
        self.sync()
        partner = self._zeffy_contact(data).partner_id
        self.assertEqual(partner.name, "Robin Roy")
        self.assertEqual(partner.email, "new.donor@example.com")
        self.assertEqual(partner.phone, "+15145550100")
        self.assertEqual(partner.street, "123 Rue Principale")
        self.assertEqual(partner.city, "Sainte-Exemple")
        self.assertEqual(partner.zip, "J0A 1B0")
        self.assertEqual(partner.state_id, self.quebec)
        self.assertEqual(partner.country_id, self.env.ref("base.ca"))
        self.assertFalse(partner.is_company)

    def test_link_is_kept_when_email_changes(self):
        data = make_contact(email="first@example.com")
        self.api.contacts = [data]
        self.sync()
        partner = self._zeffy_contact(data).partner_id
        other = self.Partner.create({"name": "Other", "email": "second@example.com"})
        data.update(email="second@example.com", updated=data["updated"] + 10)
        self.sync()
        contact = self._zeffy_contact(data)
        self.assertEqual(contact.partner_id, partner)
        self.assertNotEqual(contact.partner_id, other)
        self.assertEqual(contact.email, "second@example.com")

    def test_incremental_after_first_pass(self):
        self.api.contacts = [make_contact(updated=1767225600)]
        self.sync()
        first_params = [p for path, p in self.api.calls if path == "contacts"]
        self.assertNotIn("updated[gte]", first_params[0])
        self.api.calls.clear()
        self.sync()
        params = [p for path, p in self.api.calls if path == "contacts"]
        self.assertEqual(params[0]["updated[gte]"], 1767225600)
