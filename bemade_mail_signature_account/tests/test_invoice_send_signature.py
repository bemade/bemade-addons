"""Use case: an invoice sent from the invoice send window carries no personal
signature; the template's own signature only.

Acceptance criteria
-------------------
* Salesperson = sender, salesperson ≠ sender, credit note: the send window's
  body is the template exactly as rendered (built-in signature kept, nothing
  appended or removed), and neither the sent email nor the logged message
  contains the sender's or the salesperson's personal signature.
* A message written in the invoice's chatter is still signed (normal
  ``bemade_mail_signature`` behaviour).
"""

from markupsafe import Markup

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.bemade_mail_signature.tools import text_key
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import tagged

SENDER_SIGNATURE = Markup("<p>Sam Signer</p><p>Example Widgets Inc.</p>")
SENDER_TEXT = "Example Widgets Inc."
OTHER_SIGNATURE = Markup("<p>Olive Other</p><p>Other Widgets Ltd.</p>")
OTHER_TEXT = "Other Widgets Ltd."
TEAM_SIGNATURE = "Example Billing Team"


@tagged("post_install", "-at_install")
class TestInvoiceSendSignature(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_notify_force_send=False))
        cls.env.user.signature = SENDER_SIGNATURE
        cls.env.user.email = "sam.signer@example.com"
        cls.other_user = mail_new_test_user(
            cls.env,
            login="sig_other_account",
            name="Olive Other",
            email="olive.other@example.com",
            groups="base.group_user,account.group_account_invoice",
            company_id=cls.company_data["company"].id,
            signature=OTHER_SIGNATURE,
        )
        cls.partner_a.email = "partner_a@example.com"
        cls.template = cls.env["mail.template"].create(
            {
                "name": "Sig invoice template",
                "model_id": cls.env["ir.model"]._get_id("account.move"),
                "subject": "Invoice {{ object.name }}",
                "body_html": (
                    '<p>Here is your invoice <t t-out="object.name"/>.<br/><br/>'
                    "%s<br/>billing@example.com</p>" % TEAM_SIGNATURE
                ),
                "partner_to": "{{ object.partner_id.id }}",
                "use_default_to": False,
            }
        )

    def _wizard(self, move):
        return (
            self.env["account.move.send.wizard"]
            .with_context(active_model="account.move", active_ids=move.ids)
            .create({"template_id": self.template.id, "sending_methods": ["email"]})
        )

    def _last_comment(self, move):
        return self.env["mail.message"].search(
            [("model", "=", "account.move"), ("res_id", "=", move.id),
             ("message_type", "=", "comment")],
            order="id desc",
            limit=1,
        )

    def _check_no_personal_signature(self, move):
        wizard = self._wizard(move)
        rendered = wizard._get_default_mail_body(move, self.template, wizard.lang)
        self.assertEqual(text_key(wizard.body), text_key(rendered), "template text unchanged")
        self.assertIn(TEAM_SIGNATURE, wizard.body)
        self.assertNotIn(SENDER_TEXT, wizard.body)
        self.assertNotIn("o_bemade_mail_signature", wizard.body)
        wizard.action_send_and_print()
        message = self._last_comment(move)
        self.assertTrue(message)
        self.assertIn(TEAM_SIGNATURE, message.body)
        mails = self.env["mail.mail"].sudo().search([("mail_message_id", "=", message.id)])
        self.assertTrue(mails)
        for body in [message.body] + mails.mapped("body_html"):
            self.assertNotIn(SENDER_TEXT, body)
            self.assertNotIn(OTHER_TEXT, body)
        for mail in mails:
            self.assertIn(TEAM_SIGNATURE, mail.body_html)

    def test_salesperson_is_sender(self):
        invoice = self.init_invoice("out_invoice", amounts=[100], post=True)
        invoice.invoice_user_id = self.env.user
        self._check_no_personal_signature(invoice)

    def test_salesperson_not_sender(self):
        invoice = self.init_invoice("out_invoice", amounts=[100], post=True)
        invoice.invoice_user_id = self.other_user
        self._check_no_personal_signature(invoice)

    def test_credit_note(self):
        refund = self.init_invoice("out_refund", amounts=[100], post=True)
        refund.invoice_user_id = self.other_user
        self._check_no_personal_signature(refund)

    def test_chatter_message_still_signed(self):
        invoice = self.init_invoice("out_invoice", amounts=[100], post=True)
        message = invoice.message_post(
            body=Markup("<p>A question about your invoice</p>"),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=invoice.partner_id.ids,
        )
        self.assertIn("o_bemade_mail_signature", message.body)
        self.assertEqual(message.body.count(SENDER_TEXT), 1)
