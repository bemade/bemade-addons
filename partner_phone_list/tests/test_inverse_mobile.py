# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: writing Mobile lands in the list.

Acceptance criteria:
- Writing a new number in Mobile on a contact without numbers creates a
  Mobile line, which becomes Phone too.
- Writing a new number in Mobile on a contact with numbers inserts a Mobile
  line right after the top line: Phone does not change.
- Writing in Mobile a number already in the list retypes that line Mobile
  (no duplicate); a line already on top stays on top.
- Clearing Mobile removes the first Mobile line only.
"""

from odoo.fields import Command
from odoo.tests import tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestInverseMobile(PhoneListCase):
    def test_mobile_on_empty_contact(self):
        partner = self._partner(mobile="514-555-0102")
        self.assertEqual(self._numbers(partner), [("mobile", "+1 514-555-0102", False)])
        self.assertEqual(partner.phone, "+1 514-555-0102")
        self.assertEqual(partner.mobile, "+1 514-555-0102")

    def test_new_mobile_goes_after_top(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "fax", "number": "514-555-0109", "sequence": 2}),
            ]
        )
        partner.mobile = "514-555-0102"
        self.assertEqual(
            self._numbers(partner),
            [
                ("office", "+1 514-555-0101", False),
                ("mobile", "+1 514-555-0102", False),
                ("fax", "+1 514-555-0109", False),
            ],
        )
        self.assertEqual(partner.phone, "+1 514-555-0101")
        self.assertEqual(partner.mobile, "+1 514-555-0102")

    def test_existing_number_is_retyped(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "office", "number": "514-555-0102", "sequence": 2}),
            ]
        )
        partner.mobile = "(514) 555-0101"
        self.assertEqual(len(partner.phone_ids), 2)
        self.assertEqual(
            self._numbers(partner)[0], ("mobile", "+1 514-555-0101", False)
        )
        self.assertEqual(partner.phone, "+1 514-555-0101")
        self.assertEqual(partner.mobile, "+1 514-555-0101")

    def test_clear_mobile_removes_first_mobile_line(self):
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0102", "sequence": 2}),
                Command.create({"type": "mobile", "number": "514-555-0103", "sequence": 3}),
            ]
        )
        partner.mobile = False
        self.assertEqual(
            self._numbers(partner),
            [("office", "+1 514-555-0101", False), ("mobile", "+1 514-555-0103", False)],
        )
        self.assertEqual(partner.mobile, "+1 514-555-0103")

    def test_phone_and_mobile_in_one_create(self):
        partner = self._partner(phone="514-555-0101", mobile="514-555-0102")
        self.assertEqual(
            self._numbers(partner),
            [("office", "+1 514-555-0101", False), ("mobile", "+1 514-555-0102", False)],
        )
