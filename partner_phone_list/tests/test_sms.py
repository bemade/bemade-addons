# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: text messages go to Mobile numbers only, when SMS can be sent.

Acceptance criteria:
- ``phone_sms_available`` (contact) and ``sms_available`` (number line) are
  True only when the SMS module is installed and the company can send SMS:
  an SMS provider other than Odoo IAP is configured (e.g. Twilio), or an IAP
  account for the SMS service with a token exists for the company.
- The contact form shows the SMS button next to Mobile, next to Phone only
  when the top number is a Mobile number, and next to Mobile lines only (the
  widget reads the fields above and the line type).
- "Send SMS" on a Mobile line opens the SMS composer on the contact: the first
  Mobile line sends through the contact's Mobile field; another Mobile line
  pre-fills its own number. Other line types refuse.
"""

import unittest

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged

from .common import PhoneListCase


@tagged("post_install", "-at_install")
class TestSms(PhoneListCase):
    def setUp(self):
        super().setUp()
        if "sms.composer" not in self.env:
            raise unittest.SkipTest("sms not installed")
        service = self.env["iap.service"].search([("technical_name", "=", "sms")], limit=1)
        self.env["iap.account"].search([("service_id", "=", service.id)]).unlink()
        self.service = service

    def _iap_account(self):
        return self.env["iap.account"].create(
            {
                "service_id": self.service.id,
                "account_token": "sample-token",
                "company_ids": [Command.set(self.env.company.ids)],
            }
        )

    def test_available_follows_the_sms_account(self):
        partner = self._partner(
            phone_ids=[Command.create({"type": "mobile", "number": "514-555-0101"})]
        )
        self.assertFalse(self.Partner._phone_list_sms_available())
        partner.invalidate_recordset()
        self.assertFalse(partner.phone_sms_available)
        self.assertFalse(partner.phone_ids.sms_available)
        self._iap_account()
        partner.invalidate_recordset()
        partner.phone_ids.invalidate_recordset()
        self.assertTrue(partner.phone_sms_available)
        self.assertTrue(partner.phone_ids.sms_available)

    def test_send_sms_from_lines(self):
        self._iap_account()
        partner = self._partner(
            phone_ids=[
                Command.create({"type": "office", "number": "514-555-0101", "sequence": 1}),
                Command.create({"type": "mobile", "number": "514-555-0102", "sequence": 2}),
                Command.create({"type": "mobile", "number": "514-555-0103", "sequence": 3}),
            ]
        )
        office, first_mobile, other_mobile = partner.phone_ids.sorted("sequence")
        action = first_mobile.action_send_sms()
        self.assertEqual(action["res_model"], "sms.composer")
        self.assertEqual(action["context"]["default_res_model"], "res.partner")
        self.assertEqual(action["context"]["default_res_id"], partner.id)
        self.assertEqual(action["context"]["default_number_field_name"], "mobile")
        self.assertNotIn("default_recipient_single_number_itf", action["context"])
        action = other_mobile.action_send_sms()
        self.assertEqual(
            action["context"]["default_recipient_single_number_itf"], "+1 514-555-0103"
        )
        with self.assertRaises(UserError):
            office.action_send_sms()
