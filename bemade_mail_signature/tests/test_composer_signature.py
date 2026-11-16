"""Use case: the full composer shows the signature that will be sent.

Acceptance criteria
-------------------
* Comment mode with a template, one record: the composer body is the rendered
  template followed by the sender's signature block (editable); sending gives one
  email with the signature exactly once, and the logged message keeps it.
* The rendered template already ends with the sender's signature: nothing is
  appended, still one signature in the email.
* The user deletes the signature from the body before sending: no signature
  leaves (no path adds one that was not in the body).
* No template (signature added by default): exactly one signature in the email.
* Opened from the chatter (body already carries core's signature block,
  ``email_add_signature`` False): exactly one signature in the email.
* Log note subtype with a template: nothing appended.
* Mass mailing mode: body unchanged.
* A module turning the signature off through the rendering hook (e.g. for a
  report flow with its own fixed signature) is honoured: nothing appended,
  nothing sent.
"""

from unittest.mock import patch

from markupsafe import Markup

from odoo.addons.mail.models.mail_thread import MailThread
from odoo.tests import Form, tagged

from .common import SIGNATURE, SIGNATURE_TEXT, SignatureCommon


@tagged("post_install", "-at_install")
class TestComposerSignature(SignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.env["mail.template"].create(
            {
                "name": "Sig test template",
                "model_id": cls.env["ir.model"]._get_id("res.partner"),
                "subject": "About {{ object.name }}",
                "body_html": '<p>Dear <t t-out="object.name"/>, here is your document.</p>',
                "partner_to": str(cls.customer.id),
                "use_default_to": False,
            }
        )
        cls.template_signed = cls.template.copy(
            {
                "name": "Sig test template (prints the user signature)",
                "body_html": '<p>Dear customer.</p><div>--<br/><t t-out="user.signature"/></div>',
            }
        )

    def _composer(self, **ctx):
        context = {
            "default_model": "res.partner",
            "default_res_ids": self.record.ids,
            "default_composition_mode": "comment",
        }
        context.update(ctx)
        return Form(
            self.env["mail.compose.message"].with_user(self.sender).with_context(**context)
        )

    def _send(self, form):
        composer = form.save()
        _mails, messages = composer._action_send_mail()
        self.assertEqual(len(messages), 1)
        return messages

    def test_template_body_ends_with_signature(self):
        form = self._composer(default_template_id=self.template.id)
        self.assertIn("here is your document", form.body)
        self.assertIn(SIGNATURE_TEXT, form.body)
        self.assertTrue(
            str(form.body).rstrip().endswith("</div>"), "the signature closes the body"
        )
        self.assertLess(
            str(form.body).index("here is your document"), str(form.body).index(SIGNATURE_TEXT)
        )
        composer = form.save()
        self.assertFalse(composer.email_add_signature)
        _mails, message = composer._action_send_mail()
        self.assertSignedOnce(message)

    def test_template_already_signed(self):
        form = self._composer(default_template_id=self.template_signed.id)
        self.assertEqual(str(form.body).count(SIGNATURE_TEXT), 1)
        message = self._send(form)
        self.assertEqual(message.body.count(SIGNATURE_TEXT), 1)
        for mail in self._mails_for(message):
            self.assertEqual(self._visible(mail.body_html).count(SIGNATURE_TEXT), 1)

    def test_signature_removed_by_user(self):
        form = self._composer(default_template_id=self.template.id)
        form.body = Markup("<p>Dear customer, no signature please.</p>")
        message = self._send(form)
        self.assertNotSigned(message)

    def test_no_template_one_signature(self):
        form = self._composer(default_body=Markup("<p>Typed in the composer</p>"))
        form.partner_ids.add(self.customer)
        message = self._send(form)
        self.assertSignedOnce(message)

    def test_from_chatter_core_block_one_signature(self):
        body = Markup(
            '<div><p>From the chatter</p><br><div class="o-signature-container">'
            '<div data-o-mail-quote="1">-- <br>%s</div></div></div>'
        ) % SIGNATURE
        form = self._composer(
            default_body=body,
            default_email_add_signature=False,
            default_partner_ids=self.customer.ids,
        )
        message = self._send(form)
        self.assertEqual(message.body.count(SIGNATURE_TEXT), 1)
        mails = self._mails_for(message)
        self.assertTrue(mails)
        for mail in mails:
            self.assertEqual(self._visible(mail.body_html).count(SIGNATURE_TEXT), 1)

    def test_log_note_template_untouched(self):
        form = self._composer(
            default_template_id=self.template.id, default_subtype_xmlid="mail.mt_note"
        )
        self.assertNotIn(SIGNATURE_TEXT, form.body)

    def test_mass_mail_untouched(self):
        composer = (
            self.env["mail.compose.message"]
            .with_user(self.sender)
            .with_context(
                default_model="res.partner",
                default_res_ids=(self.record | self.customer).ids,
                default_composition_mode="mass_mail",
                default_template_id=self.template.id,
            )
            .create({})
        )
        self.assertNotIn(SIGNATURE_TEXT, composer.body)

    def test_rendering_hook_opt_out_is_honoured(self):
        original = MailThread._notify_by_email_prepare_rendering_context

        def suppressing(self, *args, **kwargs):
            values = original(self, *args, **kwargs)
            if self.env.context.get("test_suppress_signature"):
                values["email_add_signature"] = False
                values["signature"] = ""
            return values

        with patch.object(
            MailThread, "_notify_by_email_prepare_rendering_context", suppressing
        ):
            form = self._composer(
                default_template_id=self.template.id, test_suppress_signature=True
            )
            self.assertNotIn(SIGNATURE_TEXT, form.body)
            message = self._send(form)
        self.assertNotSigned(message)
