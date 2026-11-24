# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: Phone and Mobile are derived from the number list.

Acceptance criteria:
- Phone = the top line of the list (lowest sequence), as "number ext. N" when
  the line has an extension.
- Mobile = the number of the first Mobile-type line, whatever its position;
  empty when the list holds no Mobile line.
- Reordering the list (sequence) changes Phone; retyping a line changes Mobile.
- Removing every line clears Phone and Mobile.
- The sanitized number (E.164) of each line is computed with the contact's
  country; phone_sanitized on the contact prefers Mobile, then Phone.
"""

from odoo.fields import Command
from odoo.tests import tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestComputePhoneMobile(PhoneListCase):
    def test_top_line_is_phone_and_first_mobile_is_mobile(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "extension": "12", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0102", "sequence": 2}),
                Command.create({"type": "mobile", "number": "514-555-0103", "sequence": 3}),
            ]
        )
        self.assertEqual(partner.phone, "+1 514-555-0101 ext. 12")
        self.assertEqual(partner.mobile, "+1 514-555-0102")

    def test_reorder_changes_phone(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0102", "sequence": 2}),
            ]
        )
        mobile_line = partner.phone_ids.filtered(lambda l: l.type == "mobile")
        mobile_line.sequence = 0
        self.assertEqual(partner.phone, "+1 514-555-0102")
        self.assertEqual(partner.mobile, "+1 514-555-0102")

    def test_retype_changes_mobile(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0102", "sequence": 2}),
            ]
        )
        self.assertEqual(partner.mobile, "+1 514-555-0102")
        partner.phone_ids.filtered(lambda l: l.type == "mobile").type = "home"
        self.assertFalse(partner.mobile)
        partner.phone_ids.filtered(lambda l: l.type == "office").type = "mobile"
        self.assertEqual(partner.mobile, "+1 514-555-0101")

    def test_remove_all_lines_clears_phone_and_mobile(self):
        partner = self._partner(
            phone_ids=[Command.create({"type": "mobile", "number": "514-555-0102"})]
        )
        self.assertEqual(partner.phone, "+1 514-555-0102")
        partner.write({"phone_ids": [Command.clear()]})
        self.assertFalse(partner.phone)
        self.assertFalse(partner.mobile)

    def test_sanitized_number_and_phone_sanitized_prefers_mobile(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "(514) 555-0101", "sequence": 1}),
                Command.create({"type": "mobile", "number": "438.555.0102", "sequence": 2}),
            ]
        )
        office = partner.phone_ids.filtered(lambda l: l.type == "office")
        self.assertEqual(office.number_sanitized, "+15145550101")
        self.assertEqual(partner.phone_sanitized, "+14385550102")
        partner.phone_ids.filtered(lambda l: l.type == "mobile").unlink()
        self.assertEqual(partner.phone_sanitized, "+15145550101")
