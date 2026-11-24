"""Use case: the signature is BUILT for the record it goes out on, and the
composer previews that same signature.

Acceptance criteria (company signature policy on):
- AC1: the stored signature is the context-free one: {{work_email}} shows the
  user's sending address when set, the work email otherwise; changing the
  sending address regenerates it.
- AC2: chatter "Send message" on a record imposing an address (a ticket's
  team): the email's signature shows that address, not the user's; the
  stored signature is not modified.
- AC3: the layout signing with the record's responsible builds the
  responsible's signature for the record.
- AC4: a template printing ``user.signature`` with a fixed, non-personal
  sender (purchasing@) prints the signature built with that sender; with a
  placeholder sender, the stored signature. The composer (template, single
  record, ``object.user_id.signature``) gets the same.
- AC5: the chatter data the composer previews (``mailCompanySignature``) is
  the signature built for the record, only when asked for.
- AC6: policy off: the stored (hand-written) signature goes out unchanged,
  whatever the sending address or the record.
"""

from odoo.tests import Form, tagged

from odoo.addons.mail.tools.discuss import Store

from .common_sender import SenderCommon

SIG_START = "Intégrateur"


@tagged("post_install", "-at_install")
class TestSignaturePerRecord(SenderCommon):
    def setUp(self):
        super().setUp()
        self._enable()

    def test_ac1_stored_signature_context_free(self):
        self.assertIn("full@example.com", self.u_full.signature)
        self._set_alias(self.u_full, self.alias)
        self.assertIn(self.alias_email, self.u_full.signature)
        self.assertNotIn("full@example.com", self.u_full.signature)
        self._set_alias(self.u_full, False)
        self.assertIn("full@example.com", self.u_full.signature)

    def test_ac2_layout_signature_built_for_record(self):
        self._set_alias(self.u_full, self.alias)
        stored = str(self.u_full.signature)
        with self._record_override():
            _message, mail = self._post(self.u_full)
        signature = self._signature_part(mail.body_html, SIG_START)
        self.assertMentions(signature, self.override_email)
        self.assertNotMentions(signature, self.alias_email)
        self.assertNotMentions(signature, "full@example.com")
        self.assertEqual(str(self.u_full.signature), stored)

    def test_ac2_no_override_stored_signature(self):
        self._set_alias(self.u_full, self.alias)
        _message, mail = self._post(self.u_full)
        self.assertIn(self.alias_email, self._signature_part(mail.body_html, SIG_START))

    def test_ac3_responsible_layout(self):
        partner = self.env["res.partner"].create({"name": "Sender Customer", "user_id": self.u_full.id})
        with self._record_override():
            _message, mail = self._post(
                self.u_nomobile,
                record=partner,
                email_layout_xmlid="mail.mail_notification_layout_with_responsible_signature",
            )
        signature = self._signature_part(mail.body_html, SIG_START)
        self.assertMentions(signature, self.override_email)
        self.assertNotMentions(signature, "full@example.com")

    def test_ac4_template_fixed_sender(self):
        template = self._template('<p>Hello</p><t t-out="user.signature"/>', email_from=self.fixed_from)
        mail = self._send_template(template, self.u_full)
        signature = self._signature_part(mail.body_html, SIG_START)
        self.assertMentions(signature, self.fixed_from)
        self.assertNotMentions(signature, "full@example.com")
        self.assertEqual(mail.email_from, self.fixed_from, "the template's sender is kept")

    def test_ac4_fixed_sender_from_context(self):
        """The composer passes the template's sender in the context (for the
        signature block other addons build through the layout hook)."""
        signature = self.u_full.with_context(
            mail_signature_email_from=self.fixed_from
        )._mail_signature_for(self.document)
        self.assertMentions(signature, self.fixed_from)
        self.assertNotMentions(signature, "full@example.com")

    def test_ac4_template_placeholder_sender(self):
        self._set_alias(self.u_full, self.alias)
        template = self._template('<p>Write to <t t-out="user.email"/></p><t t-out="user.signature"/>')
        mail = self._send_template(template, self.u_full)
        self.assertIn(self.alias_email, self._signature_part(mail.body_html, SIG_START))
        # Outside the signature, the body is not touched.
        self.assertIn("Write to full@example.com", mail.body_html)

    def test_ac4_composer_responsible_signature(self):
        partner = self.env["res.partner"].create({"name": "Sender Customer", "user_id": self.u_full.id})
        template = self._template(
            '<p>Hello</p><t t-out="object.user_id.signature"/>', model="res.partner"
        )
        with self._record_override():
            composer = Form(
                self.env["mail.compose.message"]
                .with_user(self.u_nomobile)
                .with_context(
                    default_model="res.partner",
                    default_res_ids=partner.ids,
                    default_composition_mode="comment",
                    default_template_id=template.id,
                    default_partner_ids=self.external.ids,
                )
            ).save()
            with self.mock_mail_gateway():
                _mails, message = composer._action_send_mail()
                self.env.flush_all()
        mail = self._new_mails.filtered(lambda m: self.external in m.recipient_ids)
        self.assertMentions(str(mail.body_html), self.override_email)
        self.assertNotMentions(str(mail.body_html), "full@example.com")

    def _preview(self, user, record, request_list):
        store = Store()
        record.with_user(user)._thread_to_store(store, [], request_list=request_list)
        threads = store.get_result().get("mail.thread", [])
        return [t for t in threads if t.get("id") == record.id and "mailCompanySignature" in t]

    def test_ac5_preview_is_the_sent_signature(self):
        self._set_alias(self.u_full, self.alias)
        with self._record_override():
            preview = self._preview(self.u_full, self.document, ["mail_company_signature"])
            built = str(self.u_full._mail_signature_for(self.document))
        self.assertEqual(len(preview), 1)
        value = preview[0]["mailCompanySignature"]
        html = value[1] if isinstance(value, list) else str(value)
        self.assertEqual(html, built)
        self.assertIn(self.override_email, html)
        self.assertFalse(self._preview(self.u_full, self.document, ["followers"]))

    def test_ac6_policy_off_signature_unchanged(self):
        self._enable(enabled=False)
        hand_written = '<p>Sig sig_full, buyer</p><p><a href="mailto:full@example.com">full@example.com</a></p>'
        self.u_full.signature = hand_written
        self._set_alias(self.u_full, self.alias)
        with self._record_override():
            self.assertEqual(str(self.u_full._mail_signature_for(self.document)), hand_written)
            _message, mail = self._post(self.u_full)
        signature = self._signature_part(mail.body_html, "buyer")
        self.assertMentions(signature, "full@example.com")
        self.assertNotMentions(signature, self.override_email)
        self.assertNotMentions(signature, self.alias_email)
