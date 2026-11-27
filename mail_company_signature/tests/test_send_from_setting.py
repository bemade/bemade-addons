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
- AC4b: setting on, a template's fixed sender that is a team inbox (an Odoo
  alias, purchasing@): Reply-To becomes that same address instead of the
  catchall; a fixed sender that is not an inbox keeps core's Reply-To.
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

    def _fixed_inbox(self):
        local, _domain = self.fixed_from.split("@")
        return self.env["mail.alias"].create(
            {
                "alias_name": local,
                "alias_domain_id": self.mail_alias_domain.id,
                "alias_model_id": self.env["ir.model"]._get_id("hr.job"),
            }
        )

    def _send_fixed_by_composer(self, user, email_from):
        template = self._template("<p>Hello</p>", email_from=email_from)
        with self.mock_mail_gateway():
            composer = (
                self.env["mail.compose.message"]
                .with_user(user)
                .with_context(default_model="res.partner", default_res_ids=self.document.ids,
                              default_composition_mode="comment", default_template_id=template.id)
                .create({"partner_ids": self.external.ids})
            )
            composer._action_send_mail()
            self.env.flush_all()
        return self._new_mails.filtered(lambda m: self.external in m.recipient_ids)

    def test_ac4b_fixed_sender_inbox_reply_to(self):
        self._fixed_inbox()
        # Without the setting: core's Reply-To (catchall), for reference.
        before = self._send_fixed_by_composer(self.u_full, self.fixed_from)
        self.assertNotEqual(email_normalize(before.reply_to), self.fixed_from)
        self._setting()
        mail = self._send_fixed_by_composer(self.u_full, self.fixed_from)
        self.assertEqual(mail.email_from, self.fixed_from, "the template's sender is kept")
        self.assertEqual(email_normalize(mail.reply_to), self.fixed_from)
        sent = self._send_template(self._template("<p>Hello</p>", email_from=self.fixed_from), self.u_full)
        self.assertEqual(email_normalize(sent.reply_to), self.fixed_from)

    def test_ac4b_fixed_sender_not_inbox_kept(self):
        self._setting()
        other = "front-desk@%s" % self.alias_domain
        mail = self._send_fixed_by_composer(self.u_full, other)
        self.assertEqual(mail.email_from, other)
        self.assertNotEqual(email_normalize(mail.reply_to), other)

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
