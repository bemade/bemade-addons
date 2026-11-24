"""Use case: company setting « Send from the signature address ».

Acceptance criteria:
- AC1: setting off (default): From and Reply-To are as without this addon,
  even for a user with a sending address.
- AC2: setting on, user with a sending address: the message and its email go
  out as "Name (Team)" <inbox>, Reply-To the inbox.
- AC3: setting on, a record imposing its address (ticket): its address and
  label, Reply-To forced to it.
- AC4: setting on, a template whose sender is the user (``{{
  user.email_formatted }}``) is rewritten; a template's fixed sender
  (purchasing@) is kept.
- AC5: setting on, a user without a team address (personal) and a portal
  user: unchanged.
- AC6: the setting is per company: a user of another company is unchanged.
"""

from odoo.tests import tagged
from odoo.tools import email_normalize

from .common_sender import SenderCommon


@tagged("post_install", "-at_install")
class TestSendFromSetting(SenderCommon):
    def test_ac1_setting_off_unchanged(self):
        before, before_mail = self._post(self.u_full)
        self._set_alias(self.u_full, self.alias)
        after, after_mail = self._post(self.u_full)
        self.assertEqual(after.email_from, self.u_full.email_formatted)
        self.assertEqual(after.reply_to, before.reply_to)
        self.assertEqual(after_mail.email_from, before_mail.email_from)
        self.assertNotIn(self.alias_email, after_mail.reply_to or "")

    def test_ac2_user_sending_address(self):
        self._setting()
        self._set_alias(self.u_full, self.alias)
        message, mail = self._post(self.u_full)
        expected = '"Sig sig_full (Purchasing Team)" <%s>' % self.alias_email
        self.assertEqual(message.email_from, expected)
        self.assertEqual(email_normalize(message.reply_to), self.alias_email)
        self.assertEqual(mail.email_from, expected)
        self.assertEqual(email_normalize(mail.reply_to), self.alias_email)
        self.assertEqual(message.author_id, self.u_full.partner_id, "the author is still the person")

    def test_ac3_record_override(self):
        self._setting()
        self._set_alias(self.u_full, self.alias)
        with self._record_override():
            message, mail = self._post(self.u_full)
        self.assertEqual(message.email_from, '"Sig sig_full (Care Test)" <%s>' % self.override_email)
        self.assertEqual(email_normalize(mail.reply_to), self.override_email)

    def test_ac4_templates(self):
        self._setting()
        self._set_alias(self.u_full, self.alias)
        mail = self._send_template(self._template("<p>Hello</p>"), self.u_full)
        self.assertEqual(email_normalize(mail.email_from), self.alias_email)
        self.assertEqual(email_normalize(mail.reply_to), self.alias_email)
        fixed = self._send_template(self._template("<p>Hello</p>", email_from=self.fixed_from), self.u_full)
        self.assertEqual(fixed.email_from, self.fixed_from)

    def test_ac5_personal_and_portal_unchanged(self):
        self._setting()
        message, _mail = self._post(self.u_nomobile)
        self.assertEqual(message.email_from, self.u_nomobile.email_formatted)
        self._set_alias(self.u_portal, self.alias)
        values = {"email_from": self.u_portal.email_formatted, "author_id": self.u_portal.partner_id.id,
                  "message_type": "comment", "model": "res.partner", "res_id": self.document.id}
        self.env["mail.message"]._mail_send_from_signature_address([values])
        self.assertEqual(values["email_from"], self.u_portal.email_formatted)

    def test_ac6_other_company_unchanged(self):
        self._setting(company=self.company_b)
        self._set_alias(self.u_full, self.alias)
        message, _mail = self._post(self.u_full)
        self.assertEqual(message.email_from, self.u_full.email_formatted)
