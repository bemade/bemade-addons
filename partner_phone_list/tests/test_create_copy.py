# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: creating and duplicating contacts.

Acceptance criteria:
- A batch create mixing contacts with a list, with Phone only and with nothing
  gives each contact the right list and Phone.
- Duplicating a contact copies its list (types, extensions, labels, order).
- Deleting a contact deletes its numbers.
"""

from odoo.fields import Command
from odoo.tests import tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestCreateCopy(PhoneListCase):
    def test_batch_create(self):
        a, b, c = self.Partner.create(
            [
                {
                    "name": "Sample A",
                    "phone_ids": [
                        Command.create({"type": "direct", "number": "514-555-0111", "label": "desk"}),
                    ],
                },
                {"name": "Sample B", "phone": "514-555-0121"},
                {"name": "Sample C"},
            ]
        )
        self.assertEqual(a.phone, "+1 514-555-0111")
        self.assertEqual(self._numbers(b), [("office", "+1 514-555-0121", False)])
        self.assertEqual(b.phone, "+1 514-555-0121")
        self.assertFalse(c.phone_ids)
        self.assertFalse(c.phone)

    def test_create_with_numeric_phone(self):
        """Callers sometimes pass a number as int (imports, other modules'
        tests): it is stored as text, not a crash."""
        partner = self.env["res.partner"].create({"name": "Synthetic Int", "phone": 5145550123})
        self.assertTrue(partner.phone)
        self.assertEqual(len(partner.phone_ids), 1)
        partner.write({"mobile": 5145550124})
        self.assertTrue(partner.mobile)

    def test_copy_keeps_lines(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "extension": "7", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0102", "label": "personal", "sequence": 2}),
            ]
        )
        copy = partner.copy()
        self.assertEqual(self._numbers(copy), self._numbers(partner))
        self.assertEqual(copy.phone, "+1 514-555-0101 ext. 7")
        self.assertEqual(copy.mobile, "+1 514-555-0102")
        self.assertEqual(copy.phone_ids.mapped("label"), [False, "personal"])
        self.assertNotEqual(copy.phone_ids, partner.phone_ids)

    def test_unlink_partner_deletes_lines(self):
        partner = self._partner(phone="514-555-0101")
        line = partner.phone_ids
        partner.unlink()
        self.assertFalse(line.exists())
