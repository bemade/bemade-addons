"""Use case: a comment posted in the chatter carries the signature it is sent with.

Acceptance criteria
-------------------
* A comment (subtype Discussions) posted by an internal user who has a signature
  gets the signature block appended to its body, wrapped so the chatter folds it
  (``data-o-mail-quote="1"``); the outgoing email contains the signature exactly
  once (the notification layout does not add a second copy).
* A log note is left as core does it: nothing appended to its body.
* A caller passing ``email_add_signature=False`` gets nothing.
* A user without a signature, a portal author or a Discuss channel get nothing.
* A reply in the thread is signed again (every message).
* A post with a custom ``email_layout_xmlid`` is left to that layout.
* A body that already contains the sender's signature is not signed again, and
  the email still carries one signature.
* Any module that turns the signature off through
  ``_notify_by_email_prepare_rendering_context`` is honoured: nothing is added.
* A plain-text body stays escaped.
"""

from unittest.mock import patch

from markupsafe import Markup

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.addons.mail.models.mail_thread import MailThread
from odoo.tests import tagged

from .common import SIGNATURE, SIGNATURE_TEXT, SignatureCommon


@tagged("post_install", "-at_install")
class TestPostSignature(SignatureCommon):
    def test_comment_is_signed_and_folded(self):
        message = self._post()
        self.assertSignedOnce(message)
        self.assertTrue(message.body.startswith("<p>Hello there</p>"), message.body)
        # The flag still says "signed": the block in the body is the signature.
        self.assertTrue(message.email_add_signature)
        self.assertEqual(message.preview, "Hello there")

    def test_log_note_is_not_signed(self):
        # Log note: left exactly as core does it (body untouched; a note that
        # mentions someone keeps core's email behaviour).
        message = self._post(subtype_xmlid="mail.mt_note", partner_ids=[])
        self.assertNotSigned(message)
        self.assertTrue(message.email_add_signature)

    def test_caller_opt_out(self):
        message = self._post(email_add_signature=False)
        self.assertNotSigned(message)

    def test_user_without_signature(self):
        self.sender.signature = False
        message = self._post()
        self.assertNotSigned(message)

    def test_portal_author_untouched(self):
        portal = mail_new_test_user(
            self.env,
            login="sig_portal",
            name="Pat Portal",
            email="pat.portal@example.com",
            groups="base.group_portal",
            signature=SIGNATURE,
        )
        message = self.record.sudo().message_post(
            body=Markup("<p>From portal</p>"),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            author_id=portal.partner_id.id,
        )
        self.assertNotIn(SIGNATURE_TEXT, message.body)

    def test_reply_is_signed_again(self):
        first = self._post()
        reply = self._post(body=Markup("<p>Follow-up</p>"), parent_id=first.id)
        self.assertSignedOnce(first)
        self.assertSignedOnce(reply)

    def test_custom_layout_left_to_layout(self):
        message = self._post(email_layout_xmlid="mail.mail_notification_light")
        self.assertNotIn(SIGNATURE_TEXT, message.body)
        self.assertTrue(message.email_add_signature)

    def test_body_already_signed(self):
        body = Markup("<p>Hello</p><div>-- <br>%s</div>") % SIGNATURE
        message = self._post(body=body)
        self.assertEqual(message.body.count(SIGNATURE_TEXT), 1)
        for mail in self._mails_for(message):
            self.assertEqual(self._visible(mail.body_html).count(SIGNATURE_TEXT), 1)

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
            message = self.record.with_context(test_suppress_signature=True).with_user(
                self.sender
            ).message_post(
                body=Markup("<p>Hello</p>"),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=self.customer.ids,
            )
        self.assertNotSigned(message)

    def test_plain_text_body_stays_escaped(self):
        message = self._post(body="a < b")
        self.assertIn("a &lt; b", message.body)
        self.assertSignedOnce(message)

    def test_discuss_channel_untouched(self):
        channel = self.env["discuss.channel"].create(
            {"name": "Sig channel", "channel_type": "channel"}
        )
        channel._add_members(users=self.sender)
        message = channel.with_user(self.sender).message_post(
            body=Markup("<p>Hi team</p>"),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self.assertNotIn(SIGNATURE_TEXT, message.body)
