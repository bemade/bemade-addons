# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: other models writing a contact's phone.

Acceptance criteria:
- Writing the phone of a user or of a company (related to their contact)
  adds or promotes the number in the contact's list.
- Writing the phone of a lead linked to a contact (when CRM is installed)
  reaches the contact as a promoted line, without duplicates.
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
        self.assertEqual(self._numbers(user.partner_id), [("office", "514-555-0131", False)])
        user.partner_id.mobile = "514-555-0132"
        user.phone = "5145550132"
        self.assertEqual(len(user.partner_id.phone_ids), 2)
        self.assertEqual(user.partner_id.phone, "5145550132")

    def test_company_phone(self):
        company = self.env["res.company"].create({"name": "Sample Co", "phone": "514-555-0141"})
        self.assertEqual(company.partner_id.phone, "514-555-0141")
        company.phone = "514-555-0142"
        self.assertEqual(
            self._numbers(company.partner_id),
            [("office", "514-555-0142", False), ("office", "514-555-0141", False)],
        )

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
        self.assertEqual(lead.phone, "514-555-0151")
        lead.phone = "514-555-0152"
        self.assertEqual(len(partner.phone_ids), 2)
        self.assertEqual(partner.phone, "514-555-0152")
        self.assertEqual(lead.phone, "514-555-0152")
