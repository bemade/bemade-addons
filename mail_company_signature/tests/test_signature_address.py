"""Signature email address: the signature shows a team inbox.

Acceptance criteria:
- From and Reply-To of the emails are NOT changed by the setting: a user with
  it gets the same sender and Reply-To as without it.
- The employee's work email is the user's address here (hr syncs it).
- A hand-written signature (company policy off) that carries the user's
  personal address (mailto link and text, any case; user email, login or
  employee work email) goes out with the signature email address instead:
  in the notification layout (chatter "Send message"), in the layout signing
  with the record's responsible, in the signature block the full composer
  puts in the body, and in templates embedding ``user.signature`` or
  ``object.user_id.signature`` (composer and ``send_mail``).
- Only the signature changes: the same address elsewhere in the body stays,
  and the stored signature is not modified.
- Users without the setting and portal users: no change.
- The company signature's {{work_email}} shows the signature email address
  when set, the work email otherwise; changing the setting regenerates it.
"""

from markupsafe import Markup

from odoo.tests import Form, tagged

from .common import CompanySignatureCommon

PERSONAL_SIGNATURE = (
    '<p>Sig Full, buyer</p><p><a href="mailto:Full@Example.com">'
    "FULL@example.com</a></p><p>Direct: full@example.com</p>"
)
QUOTE_BLOCK = (
    '<div data-o-mail-quote="1">-- <br><p>Sig Full</p><p><a href="mailto:'
    'full@example.com">full@example.com</a></p></div>'
)


@tagged("post_install", "-at_install")
class TestSignatureAddress(CompanySignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.external = cls.env["res.partner"].create(
            {"name": "Sigaddr Supplier", "email": "sigaddr.supplier@example.com"}
        )
        cls.record = cls.env["res.partner"].create({"name": "Sigaddr Document"})
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "purchasing-test",
                "alias_domain_id": cls.mail_alias_domain.id,
                "alias_model_id": cls.env["ir.model"]._get_id("hr.job"),
            }
        )
        cls.alias_email = "purchasing-test@%s" % cls.alias_domain
        cls.u_full.signature = PERSONAL_SIGNATURE

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _set(self, user, alias):
        user.sudo().mail_send_as_alias_id = alias
        self.env.flush_all()

    def _post(self, user, record=None, **kwargs):
        record = record or self.record
        kwargs.setdefault("body", "Bonjour")
        with self.mock_mail_gateway():
            message = record.with_user(user).message_post(
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=self.external.ids,
                **kwargs,
            )
            self.env.flush_all()
        mail = self._new_mails.filtered(lambda m: self.external in m.recipient_ids)
        self.assertEqual(len(mail), 1)
        return message, mail

    def _assert_signature_rewritten(self, html, user=None):
        user = user or self.u_full
        self.assertIn('href="mailto:%s"' % self.alias_email, html)
        self.assertIn(user._mail_outgoing_signature(), html)
        self.assertNotIn(PERSONAL_SIGNATURE, html)

    # ------------------------------------------------------------------
    # Sender and Reply-To are not changed
    # ------------------------------------------------------------------
    def test_from_and_reply_to_unchanged(self):
        before, before_mail = self._post(self.u_full)
        self._set(self.u_full, self.alias)
        after, after_mail = self._post(self.u_full)
        self.assertEqual(after.email_from, self.u_full.email_formatted)
        self.assertEqual(after.email_from, before.email_from)
        self.assertEqual(after.reply_to, before.reply_to)
        self.assertEqual(after_mail.email_from, before_mail.email_from)
        self.assertEqual(after_mail.reply_to, before_mail.reply_to)
        self.assertNotIn(self.alias_email, after_mail.reply_to or "")

    def test_template_from_and_reply_to_unchanged(self):
        self._set(self.u_full, self.alias)
        template = self._template("<p>Hello</p>")
        template.email_to = self.external.email
        mail = self.env["mail.mail"].sudo().browse(
            template.with_user(self.u_full).send_mail(self.record.id)
        )
        self.assertEqual(mail.email_from, self.u_full.email_formatted)
        self.assertNotIn(self.alias_email, mail.reply_to or "")

    # ------------------------------------------------------------------
    # Notification layout
    # ------------------------------------------------------------------
    def test_chatter_signature_shows_address(self):
        self._set(self.u_full, self.alias)
        _message, mail = self._post(
            self.u_full, body=Markup("<p>Copy to full@example.com please</p>")
        )
        self._assert_signature_rewritten(mail.body_html)
        # The address outside the signature is kept.
        self.assertIn("Copy to full@example.com please", mail.body_html)
        # The stored signature is not modified.
        self.assertEqual(str(self.u_full.signature), PERSONAL_SIGNATURE)

    def test_outgoing_signature_replaces_every_personal_address(self):
        self._set(self.u_full, self.alias)
        outgoing = str(self.u_full._mail_outgoing_signature())
        self.assertNotIn("full@example.com", outgoing.lower())
        self.assertEqual(outgoing.count(self.alias_email), 3)
        # Another address merely containing the personal one is kept.
        text = self.u_full._mail_signature_replace_emails(
            "xfull@example.com, full@example.com.au, sig.full@example.com", self.alias_email
        )
        self.assertEqual(text, "xfull@example.com, full@example.com.au, sig.full@example.com")

    def test_user_without_setting_unchanged(self):
        _message, mail = self._post(self.u_full)
        self.assertIn(PERSONAL_SIGNATURE, mail.body_html)
        self.assertNotIn(self.alias_email, mail.body_html)

    def test_portal_user_never_rewritten(self):
        self._set(self.u_portal, self.alias)
        self.assertFalse(self.u_portal._mail_signature_email())
        self.assertEqual(self.u_portal._mail_outgoing_signature(), self.u_portal.signature)

    def test_responsible_signature_layout(self):
        """Layout signing with the record's responsible (sale orders)."""
        self._set(self.u_full, self.alias)
        self.record.user_id = self.u_full
        _message, mail = self._post(
            self.u_nomobile,
            email_layout_xmlid="mail.mail_notification_layout_with_responsible_signature",
        )
        self._assert_signature_rewritten(mail.body_html)

    # ------------------------------------------------------------------
    # Full composer: signature block in the body
    # ------------------------------------------------------------------
    def test_full_composer_signature_block(self):
        self._set(self.u_full, self.alias)
        body = Markup("<p>Write to full@example.com</p>" + QUOTE_BLOCK)
        message, mail = self._post(self.u_full, body=body, email_add_signature=False)
        self.assertIn("Write to full@example.com", message.body)
        self.assertIn('href="mailto:%s"' % self.alias_email, message.body)
        self.assertEqual(message.body.count("full@example.com"), 1)
        self.assertIn('href="mailto:%s"' % self.alias_email, mail.body_html)

    def test_full_composer_block_without_setting_unchanged(self):
        body = Markup("<p>Hi</p>" + QUOTE_BLOCK)
        message, _mail = self._post(self.u_full, body=body, email_add_signature=False)
        self.assertEqual(message.body.count("full@example.com"), 2)
        self.assertNotIn(self.alias_email, message.body)

    # ------------------------------------------------------------------
    # Templates embedding a signature
    # ------------------------------------------------------------------
    def _template(self, body_html):
        return self.env["mail.template"].create(
            {
                "name": "Sigaddr template",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "subject": "Your quote",
                "body_html": body_html,
                "email_from": "{{ user.email_formatted }}",
                "use_default_to": False,
            }
        )

    def test_template_user_signature_send_mail(self):
        self._set(self.u_full, self.alias)
        template = self._template(
            '<p>Write to <t t-out="user.email"/></p><t t-out="user.signature"/>'
        )
        template.email_to = self.external.email
        mail = self.env["mail.mail"].sudo().browse(
            template.with_user(self.u_full).send_mail(self.record.id)
        )
        self._assert_signature_rewritten(mail.body_html)
        self.assertIn("Write to full@example.com", mail.body_html)

    def test_template_responsible_signature_in_composer(self):
        """``object.user_id.signature`` rendered by another user."""
        self._set(self.u_full, self.alias)
        self.record.user_id = self.u_full
        template = self._template('<p>Hello</p><t t-out="object.user_id.signature"/>')
        composer = Form(
            self.env["mail.compose.message"]
            .with_user(self.u_nomobile)
            .with_context(
                default_model="res.partner",
                default_res_ids=self.record.ids,
                default_composition_mode="comment",
                default_template_id=template.id,
                default_partner_ids=self.external.ids,
            )
        ).save()
        with self.mock_mail_gateway():
            _mails, message = composer._action_send_mail()
            self.env.flush_all()
        self._assert_signature_rewritten(message.body)
        mail = self._new_mails.filtered(lambda m: self.external in m.recipient_ids)
        self._assert_signature_rewritten(mail.body_html)

    def test_template_without_setting_unchanged(self):
        template = self._template('<t t-out="user.signature"/>')
        template.email_to = self.external.email
        mail = self.env["mail.mail"].sudo().browse(
            template.with_user(self.u_full).send_mail(self.record.id)
        )
        self.assertIn(PERSONAL_SIGNATURE, mail.body_html)

    # ------------------------------------------------------------------
    # Company signature placeholder
    # ------------------------------------------------------------------
    def test_signature_work_email_shows_address(self):
        self._enable()
        self.assertIn("full@example.com", self.u_full.signature)
        self._set(self.u_full, self.alias)
        self.assertIn(self.alias_email, self.u_full.signature)
        self.assertNotIn("full@example.com", self.u_full.signature)
        self._set(self.u_full, False)
        self.assertIn("full@example.com", self.u_full.signature)
        self.assertNotIn(self.alias_email, self.u_full.signature)
