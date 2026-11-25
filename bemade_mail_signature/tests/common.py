import re

from markupsafe import Markup

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import TransactionCase

# Synthetic data only: this repository is public.
SIGNATURE = Markup("<p>Sam Signer<br>Example Widgets Inc.</p>")
SIGNATURE_TEXT = "Example Widgets Inc."
OTHER_SIGNATURE = Markup("<p>Olive Other</p><p>Other Widgets Ltd.</p>")
OTHER_SIGNATURE_TEXT = "Other Widgets Ltd."


class SignatureCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_notify_force_send=False))
        cls.sender = mail_new_test_user(
            cls.env,
            login="sig_sender",
            name="Sam Signer",
            email="sam.signer@example.com",
            groups="base.group_user,base.group_partner_manager",
            notification_type="email",
            signature=SIGNATURE,
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Casey Customer", "email": "casey.customer@example.com"}
        )
        cls.record = cls.env["res.partner"].create(
            {"name": "Record Thread", "email": "record.thread@example.com"}
        )

    @staticmethod
    def _visible(body_html):
        """Email body without the hidden inbox preview (pre-header) text."""
        return re.sub(r'<div style="display: none;.*?</div>', "", body_html, count=1, flags=re.S)

    def _mails_for(self, message):
        return self.env["mail.mail"].sudo().search([("mail_message_id", "=", message.id)])

    def _post(self, user=None, **kwargs):
        values = {
            "body": Markup("<p>Hello there</p>"),
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",
            "partner_ids": self.customer.ids,
        }
        values.update(kwargs)
        return self.record.with_user(user or self.sender).message_post(**values)

    def assertSignedOnce(self, message):
        """The logged body ends with one folded block and one email carries it once."""
        self.assertEqual(message.body.count(SIGNATURE_TEXT), 1, message.body)
        self.assertIn('data-o-mail-quote="1"', message.body)
        self.assertIn("o_bemade_mail_signature", message.body)
        mails = self._mails_for(message)
        self.assertTrue(mails, "an email must leave")
        for mail in mails:
            # Whole email, hidden pre-header included.
            self.assertEqual(mail.body_html.count(SIGNATURE_TEXT), 1, mail.body_html)

    def assertNotSigned(self, message):
        self.assertNotIn(SIGNATURE_TEXT, message.body or "")
        for mail in self._mails_for(message):
            self.assertNotIn(SIGNATURE_TEXT, self._visible(mail.body_html))
