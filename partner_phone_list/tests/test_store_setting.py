# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: storing numbers in the international format is a setting.

Acceptance criteria:
- The setting « Store phone numbers in international format » shows in the
  general settings (Contacts) and is off on a new database.
- Off: a number written by code (create / write of the contact's Phone or
  Mobile, create / write of a number line) is stored as written (trimmed),
  like the standard Phone field: ``+15145550100`` stays ``+15145550100``.
  An extension typed after the number still goes to the extension column.
- Off: writing a number already in the list in another format still matches
  it (no duplicate) and moves it to the top.
- Off: the form still formats a number typed in the number list (onchange).
- On: the same writes store the number formatted (``+1 514-555-0100``).
"""

from odoo.tests import Form, tagged

from .common import PhoneListCase

PARAM = "partner_phone_list.store_international"


@tagged("post_install", "-at_install")
class TestStoreSetting(PhoneListCase):
    def setUp(self):
        super().setUp()
        # the default of a new database
        self.env["ir.config_parameter"].sudo().set_param(PARAM, False)

    def test_setting_off_by_default_and_in_settings(self):
        settings = Form(self.env["res.config.settings"])
        self.assertFalse(settings.partner_phone_list_store_international)
        settings.partner_phone_list_store_international = True
        settings.save().execute()
        self.assertTrue(self.Partner._phone_list_store_international())
        settings = Form(self.env["res.config.settings"])
        self.assertTrue(settings.partner_phone_list_store_international)
        settings.partner_phone_list_store_international = False
        settings.save().execute()
        self.assertFalse(self.Partner._phone_list_store_international())

    def test_off_contact_writes_stored_as_written(self):
        partner = self._partner(phone="+15145550100")
        self.assertEqual(partner.phone, "+15145550100")
        self.assertEqual(self._numbers(partner), [("office", "+15145550100", False)])
        partner.mobile = " 514.555.0102 "
        self.assertEqual(partner.mobile, "514.555.0102")
        partner.phone = "5145550103 x 7"
        self.assertEqual(partner.phone, "5145550103 ext. 7")
        self.assertEqual(
            self._numbers(partner),
            [
                ("office", "5145550103", "7"),
                ("office", "+15145550100", False),
                ("mobile", "514.555.0102", False),
            ],
        )

    def test_off_line_writes_stored_as_written(self):
        partner = self._partner()
        line = self.Line.create({"partner_id": partner.id, "number": "5145550101"})
        self.assertEqual(line.number, "5145550101")
        self.assertEqual(line.number_sanitized, "+15145550101")
        line.number = "(514) 555-0102"
        self.assertEqual(line.number, "(514) 555-0102")
        self.assertEqual(partner.phone, "(514) 555-0102")

    def test_off_matches_other_format_without_duplicate(self):
        partner = self._partner(phone="514-555-0101")
        partner.mobile = "514-555-0102"
        partner.phone = "5145550102"
        self.assertEqual(len(partner.phone_ids), 2)
        self.assertEqual(partner.phone, "5145550102")
        self.assertEqual(partner.mobile, "5145550102")

    def test_off_form_still_formats_typed_number(self):
        partner = self._partner()
        with Form(partner) as form:
            with form.phone_ids.new() as line:
                line.number = "5145550104"
                self.assertEqual(line.number, "+1 514-555-0104")
        self.assertEqual(partner.phone, "+1 514-555-0104")

    def test_on_writes_are_formatted(self):
        self.env["ir.config_parameter"].sudo().set_param(PARAM, True)
        partner = self._partner(phone="+15145550100")
        self.assertEqual(partner.phone, "+1 514-555-0100")
        line = self.Line.create({"partner_id": partner.id, "number": "5145550101"})
        self.assertEqual(line.number, "+1 514-555-0101")
