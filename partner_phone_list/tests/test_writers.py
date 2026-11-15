# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: other models writing a contact's phone.

Acceptance criteria:
- Writing the phone of a user or of a company (related to their contact)
  adds or promotes the number in the contact's list.
- Writing the phone of a lead linked to a contact (when CRM is installed)
  reaches the contact as a promoted line, without duplicates.
- Numbers are stored formatted on the contact; when the lead's phone and the
  contact's Phone differ only in format, the lead does not flag "the
  contact's phone will be updated", and writing the lead's phone again
  changes nothing on the contact (no loop, no new line, no reorder).
"""

import unittest

from odoo.fields import Command
from odoo.tests import tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestWriters(PhoneListCase):
    def test_user_phone(self):
        user = self.env["res.users"].create(
            {"name": "Sample User", "login": "sample_phone_user", "phone": "514-555-0131"}
        )
        self.assertEqual(self._numbers(user.partner_id), [("office", "+1 514-555-0131", False)])
        user.partner_id.mobile = "514-555-0132"
        user.phone = "5145550132"
        self.assertEqual(len(user.partner_id.phone_ids), 2)
        self.assertEqual(user.partner_id.phone, "+1 514-555-0132")

    def test_company_phone(self):
        company = self.env["res.company"].create(
            {"name": "Sample Co", "country_id": self.canada.id, "phone": "514-555-0141"}
        )
        self.assertEqual(company.partner_id.phone, "+1 514-555-0141")
        company.phone = "514-555-0142"
        self.assertEqual(
            self._numbers(company.partner_id),
            [("office", "+1 514-555-0142", False), ("office", "+1 514-555-0141", False)],
        )
        self.assertEqual(company.phone, "+1 514-555-0142")

    def test_lead_phone(self):
        if "crm.lead" not in self.env:
            raise unittest.SkipTest("crm not installed")
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0151", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0152", "sequence": 2}),
            ]
        )
        lead = self.env["crm.lead"].create({"name": "Sample lead", "partner_id": partner.id})
        self.assertEqual(lead.phone, "+1 514-555-0151")
        lead.phone = "5145550152"
        self.assertEqual(len(partner.phone_ids), 2)
        self.assertEqual(partner.phone, "+1 514-555-0152")
        self.env.flush_all()
        lead.invalidate_recordset()
        self.assertFalse(lead.partner_phone_update)
        # writing the same number again: nothing moves on the contact
        before = self._numbers(partner)
        lead.write({"phone": "514 555 0152"})
        self.assertEqual(self._numbers(partner), before)
        self.assertFalse(lead.partner_phone_update)
