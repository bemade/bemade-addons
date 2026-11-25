# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: writing Phone lands in the list.

Acceptance criteria:
- Writing a new number in Phone inserts it at the top of the list, typed
  Office; the other numbers are kept, below it.
- Writing a number already in the list, in another format
  (5145550101 vs +1 514-555-0101), moves that line to the top without creating
  a duplicate (its type is kept, its number takes the written format).
- A trailing extension ("x12", "ext. 12", "poste 12", "#12") is stored in the
  line's extension; Phone reads "number ext. 12".
- Clearing Phone removes the top line only.
- When the list and Phone are written together, the list wins.
- Writing the same value again is a no-op (idempotent).
"""

from odoo.fields import Command
from odoo.tests import tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestInversePhone(PhoneListCase):
    def test_new_number_goes_on_top_as_office(self):
        partner = self._partner(
            phone_ids=[Command.create({"type": "mobile", "number": "514-555-0102"})]
        )
        partner.phone = "514-555-0101"
        self.assertEqual(
            self._numbers(partner),
            [("office", "+1 514-555-0101", False), ("mobile", "+1 514-555-0102", False)],
        )
        self.assertEqual(partner.phone, "+1 514-555-0101")
        self.assertEqual(partner.mobile, "+1 514-555-0102")

    def test_existing_number_other_format_is_promoted_not_duplicated(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "mobile", "number": "5145550102", "sequence": 2}),
            ]
        )
        partner.phone = "+1 514-555-0102"
        self.assertEqual(
            self._numbers(partner),
            [("mobile", "+1 514-555-0102", False), ("office", "+1 514-555-0101", False)],
        )
        self.assertEqual(partner.phone, "+1 514-555-0102")
        # idempotent
        partner.phone = "+1 514-555-0102"
        self.assertEqual(len(partner.phone_ids), 2)

    def test_extension_is_parsed(self):
        partner = self._partner()
        for written, ext in (
            ("514-555-0101 x12", "12"),
            ("514-555-0101 ext. 13", "13"),
            ("514-555-0101 poste 14", "14"),
            ("514-555-0101 #15", "15"),
        ):
            partner.phone = written
            self.assertEqual(partner.phone_ids.sorted("sequence")[0].extension, ext)
            self.assertEqual(partner.phone, "+1 514-555-0101 ext. %s" % ext)
        # same number, four extensions = four lines
        self.assertEqual(len(partner.phone_ids), 4)

    def test_clearing_phone_removes_top_line_only(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0102", "sequence": 2}),
            ]
        )
        partner.phone = False
        self.assertEqual(self._numbers(partner), [("mobile", "+1 514-555-0102", False)])
        self.assertEqual(partner.phone, "+1 514-555-0102")

    def test_list_wins_over_phone_in_same_write(self):
        partner = self._partner(phone="514-555-0101")
        partner.write(
            {
                "phone": "514-555-0199",
                "phone_ids": [Command.create({"type": "mobile", "number": "514-555-0102", "sequence": 0})],
            }
        )
        self.assertEqual(
            self._numbers(partner),
            [("mobile", "+1 514-555-0102", False), ("office", "+1 514-555-0101", False)],
        )
        self.assertEqual(partner.phone, "+1 514-555-0102")
