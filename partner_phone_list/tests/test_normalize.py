# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: every number is stored in the international format (setting
« Store phone numbers in international format » on; see test_store_setting
for the default).

Acceptance criteria:
- A number written from code (create or write of a number line, a write of
  Phone or Mobile on the contact, a write of a user's or a company's phone) is
  stored formatted with phone_validation in the international form, using the
  contact's country, or the company's country when the contact has none:
  ``5145550101`` -> ``+1 514-555-0101``.
- A number of another country keeps its own country code.
- A value that does not parse, or whose parsing would drop or change digits
  (trailing text, two numbers glued together), is kept as typed (trimmed).
- An extension typed in the number ("x12") still goes to the extension
  column; Phone reads "+1 514-555-0101 ext. 12".
- Writing a number already in the list in another format matches it: no
  duplicate, and the stored number stays formatted.
"""

from odoo.fields import Command
from odoo.tests import tagged

from ..tools import format_number
from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestNormalize(PhoneListCase):
    def test_format_number_helper(self):
        self.assertEqual(format_number("5145550101", "CA", 1), "+1 514-555-0101")
        self.assertEqual(format_number("(514) 5550101", "CA", 1), "+1 514-555-0101")
        self.assertEqual(format_number(" +1 514 555 0101 ", "CA", 1), "+1 514-555-0101")
        self.assertEqual(format_number("+33 1 23 45 67 89", "CA", 1), "+33 1 23 45 67 89")
        self.assertEqual(format_number(" call reception ", "CA", 1), "call reception")
        # parsing would drop the trailing digits: kept as typed
        self.assertEqual(format_number("514-555-0101, 456", "CA", 1), "514-555-0101, 456")
        self.assertFalse(format_number(False, "CA", 1))

    def test_line_create_and_write_are_formatted(self):
        partner = self._partner()
        line = self.Line.create({"partner_id": partner.id, "number": "5145550101"})
        self.assertEqual(line.number, "+1 514-555-0101")
        self.assertEqual(line.number_sanitized, "+15145550101")
        line.number = "(514) 555-0102 x 7"
        self.assertEqual((line.number, line.extension), ("+1 514-555-0102", "7"))
        self.assertEqual(partner.phone, "+1 514-555-0102 ext. 7")
        line.number = "ask reception"
        self.assertEqual(line.number, "ask reception")

    def test_company_country_fallback(self):
        partner = self._partner(country_id=False)
        self.env.company.country_id = self.canada
        partner.phone = "514 555 0101"
        self.assertEqual(partner.phone, "+1 514-555-0101")

    def test_phone_and_mobile_writes_are_formatted(self):
        partner = self._partner(phone="5145550101")
        self.assertEqual(partner.phone, "+1 514-555-0101")
        partner.mobile = "514.555.0102"
        self.assertEqual(
            self._numbers(partner),
            [("office", "+1 514-555-0101", False), ("mobile", "+1 514-555-0102", False)],
        )
        self.assertEqual(partner.mobile, "+1 514-555-0102")
        # same number, other format: promoted, not duplicated, still formatted
        partner.phone = "514-555-0102"
        self.assertEqual(
            self._numbers(partner),
            [("mobile", "+1 514-555-0102", False), ("office", "+1 514-555-0101", False)],
        )
        self.assertEqual(partner.phone, "+1 514-555-0102")
        partner.phone = "5145550101 poste 22"
        self.assertEqual(partner.phone, "+1 514-555-0101 ext. 22")

    def test_create_with_lines_is_formatted(self):
        partner = self._partner(
            phone_ids=[Command.create({"type": "mobile", "number": "438 555 0103"})]
        )
        self.assertEqual(partner.phone, "+1 438-555-0103")
        self.assertEqual(partner.mobile, "+1 438-555-0103")

    def test_user_and_company_phone_are_formatted(self):
        user = self.env["res.users"].create(
            {"name": "Sample Format User", "login": "sample_format_user", "phone": "5145550104"}
        )
        self.assertEqual(user.partner_id.phone, "+1 514-555-0104")
        self.assertEqual(user.phone, "+1 514-555-0104")
