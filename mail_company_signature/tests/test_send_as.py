"""Send emails as a team inbox.

Acceptance criteria:
- A user with "Send emails as" set posts in a chatter: the message and the
  email sent go out as "User Name (Team)" <team inbox>, Reply-To the same.
- A user without the setting: sender and Reply-To unchanged.
- Full composer / templates: a sender rendered as the user's own address
  (``{{ user.email_formatted }}``) is rewritten; a fixed other address (a
  purchasing@ style template) is left alone. mail.template.send_mail too.
- The label is the alias's parent record name, else the alias local part.
- The company signature's {{work_email}} shows the team inbox when set, the
  work email otherwise; changing the setting regenerates the signature.
- An incoming reply addressed to the team inbox, with In-Reply-To of the sent
  message, lands on the same document even though the inbox is the alias of
  another model (core would read it as a forward and create a record).
"""

from odoo.tests import Form, tagged
from odoo.tools import email_normalize, formataddr, mute_logger

from .common import CompanySignatureCommon

REPLY_TEMPLATE = """Return-Path: {return_path}
To: {to}
cc: {cc}
From: {email_from}
Subject: {subject}
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Date: {date}
Message-ID: {msg_id}
{extra}
Thank you, see the attached quote.
"""


@tagged("post_install", "-at_install")
class TestSendAs(CompanySignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.external = cls.env["res.partner"].create(
            {"name": "Sendas Supplier", "email": "sendas.supplier@example.com"}
        )
        cls.record = cls.env["res.partner"].create({"name": "Sendas Document"})
        cls.team = cls.env["hr.department"].create({"name": "Purchasing Test"})
        IrModel = cls.env["ir.model"]
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "purchasing-test",
                "alias_domain_id": cls.mail_alias_domain.id,
                "alias_model_id": IrModel._get_id("hr.job"),
                "alias_parent_model_id": IrModel._get_id("hr.department"),
                "alias_parent_thread_id": cls.team.id,
            }
        )
        cls.alias_email = "purchasing-test@%s" % cls.alias_domain
        cls.bare_alias = cls.env["mail.alias"].create(
            {
                "alias_name": "orders-test",
                "alias_domain_id": cls.mail_alias_domain.id,
                "alias_model_id": IrModel._get_id("hr.job"),
            }
        )
        cls.expected_sender = formataddr(("Sig sig_full (Purchasing Test)", cls.alias_email))
        # Over 68 characters: Reply-To falls back on the bare address, like
        # core's _notify_get_reply_to_formatted_email (header folding).
        cls.expected_reply_to = cls.alias_email

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _set_send_as(self, user, alias):
        user.sudo().mail_send_as_alias_id = alias
        self.env.flush_all()

    def _post(self, user, **kwargs):
        with self.mock_mail_gateway():
            message = self.record.with_user(user).message_post(
                body="Bonjour",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=self.external.ids,
                **kwargs,
            )
            self.env.flush_all()
        mail = self._new_mails.filtered(lambda m: self.external in m.recipient_ids)
        self.assertEqual(len(mail), 1)
        return message, mail

    # ------------------------------------------------------------------
    # Chatter
    # ------------------------------------------------------------------
    def test_chatter_post_sends_as_team_inbox(self):
        self._set_send_as(self.u_full, self.alias)
        message, mail = self._post(self.u_full)
        self.assertEqual(message.email_from, self.expected_sender)
        self.assertEqual(message.reply_to, self.expected_reply_to)
        self.assertEqual(message.author_id, self.u_full.partner_id)
        self.assertEqual(mail.email_from, self.expected_sender)
        self.assertEqual(mail.reply_to, self.expected_reply_to)
        sent = [m for m in self._mails if self.external.email in m["email_to"][0]]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["email_from"], self.expected_sender)
        self.assertEqual(sent[0]["reply_to"], self.expected_reply_to)

    def test_user_without_send_as_unchanged(self):
        message, mail = self._post(self.u_nomobile)
        self.assertEqual(message.email_from, self.u_nomobile.email_formatted)
        self.assertNotIn(self.alias_email, message.reply_to or "")
        self.assertEqual(mail.email_from, self.u_nomobile.email_formatted)

    def test_label_falls_back_on_alias_name(self):
        self._set_send_as(self.u_full, self.bare_alias)
        message, mail = self._post(self.u_full)
        expected = formataddr(("Sig sig_full (orders-test)", "orders-test@%s" % self.alias_domain))
        self.assertEqual(message.email_from, expected)
        # Short enough: Reply-To keeps the name too.
        self.assertEqual(message.reply_to, expected)
        self.assertEqual(mail.reply_to, expected)

    def test_explicit_other_sender_unchanged(self):
        self._set_send_as(self.u_full, self.alias)
        message, mail = self._post(self.u_full, email_from="purchasing-fixed@example.com")
        self.assertEqual(message.email_from, "purchasing-fixed@example.com")
        self.assertEqual(mail.email_from, "purchasing-fixed@example.com")

    def test_internal_note_by_other_user_not_rewritten_for_author(self):
        """The rewrite follows the message author, not the user who posts."""
        self._set_send_as(self.u_full, self.alias)
        message = self.record.with_user(self.u_nomobile).message_post(
            body="Note", message_type="comment", subtype_xmlid="mail.mt_note"
        )
        self.assertEqual(message.email_from, self.u_nomobile.email_formatted)

    # ------------------------------------------------------------------
    # Composer and templates
    # ------------------------------------------------------------------
    def _template(self, email_from):
        return self.env["mail.template"].create(
            {
                "name": "Sendas template",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "subject": "Your quote",
                "body_html": "<p>Hello</p>",
                "email_from": email_from,
                "use_default_to": False,
            }
        )

    def _send_composer(self, template):
        composer_form = Form(
            self.env["mail.compose.message"]
            .with_user(self.u_full)
            .with_context(
                default_model="res.partner",
                default_res_ids=self.record.ids,
                default_composition_mode="comment",
                default_template_id=template.id,
                default_partner_ids=self.external.ids,
            )
        )
        composer = composer_form.save()
        with self.mock_mail_gateway():
            _mail, message = composer._action_send_mail()
            self.env.flush_all()
        mail = self._new_mails.filtered(lambda m: self.external in m.recipient_ids)
        return message, mail

    def test_composer_user_email_template_rewritten(self):
        self._set_send_as(self.u_full, self.alias)
        message, mail = self._send_composer(self._template("{{ user.email_formatted }}"))
        self.assertEqual(message.email_from, self.expected_sender)
        self.assertEqual(message.reply_to, self.expected_reply_to)
        self.assertEqual(mail.email_from, self.expected_sender)
        self.assertEqual(mail.reply_to, self.expected_reply_to)

    def test_composer_fixed_sender_template_unchanged(self):
        self._set_send_as(self.u_full, self.alias)
        message, mail = self._send_composer(self._template("purchasing-fixed@example.com"))
        self.assertEqual(message.email_from, "purchasing-fixed@example.com")
        self.assertEqual(mail.email_from, "purchasing-fixed@example.com")

    def test_template_send_mail_rewritten(self):
        self._set_send_as(self.u_full, self.alias)
        template = self._template("{{ user.email_formatted }}")
        template.email_to = self.external.email
        with self.mock_mail_gateway():
            mail_id = template.with_user(self.u_full).send_mail(self.record.id)
        mail = self.env["mail.mail"].sudo().browse(mail_id)
        self.assertEqual(mail.email_from, self.expected_sender)
        self.assertEqual(mail.reply_to, self.expected_reply_to)

    # ------------------------------------------------------------------
    # Signature
    # ------------------------------------------------------------------
    def test_signature_work_email_shows_team_inbox(self):
        self._enable()
        self.assertIn("full@example.com", self.u_full.signature)
        self._set_send_as(self.u_full, self.alias)
        self.assertIn(self.alias_email, self.u_full.signature)
        self.assertNotIn("full@example.com", self.u_full.signature)
        self._set_send_as(self.u_full, False)
        self.assertIn("full@example.com", self.u_full.signature)
        self.assertNotIn(self.alias_email, self.u_full.signature)

    def test_signature_in_sent_email_shows_team_inbox(self):
        self._enable()
        self._set_send_as(self.u_full, self.alias)
        _message, mail = self._post(self.u_full)
        self.assertIn(self.alias_email, mail.body_html)
        # Only the signature is checked: a sibling addon may show the author's
        # address in its own header block (bemade_mail_author_visibility).
        self.assertNotIn("full@example.com", self.u_full.signature)

    # ------------------------------------------------------------------
    # Incoming replies
    # ------------------------------------------------------------------
    def _reply(self, message, to, subject):
        return self.format_and_process(
            REPLY_TEMPLATE,
            self.external.email_formatted,
            to,
            subject=subject,
            extra="In-Reply-To: %s\nReferences: %s\n" % (message.message_id, message.message_id),
            target_model="hr.job",
            target_field="name",
        )

    def test_reply_to_team_inbox_lands_on_document(self):
        self._set_send_as(self.u_full, self.alias)
        message, _mail = self._post(self.u_full)
        created = self._reply(message, self.alias_email, "Re: Sendas reply")
        self.assertFalse(created, "the reply must not open a record through the alias")
        reply = self.record.message_ids.filtered(lambda m: m.subject == "Re: Sendas reply")
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply.parent_id, message)
        self.assertEqual(reply.message_type, "email")

    @mute_logger("odoo.addons.mail.models.mail_thread")
    def test_mail_to_alias_not_sent_as_still_forward(self):
        """Without the send-as, core's forward rule is untouched."""
        message, _mail = self._post(self.u_nomobile)
        self.assertNotEqual(email_normalize(message.reply_to), self.alias_email)
        created = self._reply(message, self.alias_email, "Fwd: Sendas forward")
        self.assertEqual(len(created), 1)
