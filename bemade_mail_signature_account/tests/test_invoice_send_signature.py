"""Use case: an invoice sent through the send wizard carries one signature, the
sender's, shown in the wizard before sending.

Acceptance criteria
-------------------
* The invoice's salesperson is another user: the wizard body has the sender's
  signature block once and not the salesperson's signature; the sent email and
  the logged message carry the sender's signature exactly once.
* The salesperson is the sender: one signature (the folded block).
* A credit note follows the same rule.
* The sender removes the signature from the wizard body: no signature leaves.
"""

from markupsafe import Markup

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import tagged

SENDER_SIGNATURE = Markup("<p>Sam Signer</p><p>Example Widgets Inc.</p>")
SENDER_TEXT = "Example Widgets Inc."
OTHER_SIGNATURE = Markup("<p>Olive Other</p><p>Other Widgets Ltd.</p>")
OTHER_TEXT = "Other Widgets Ltd."


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
                    '<p>Here is your invoice <t t-out="object.name"/>.</p>'
                    '<div>--<br/><t t-out="object.invoice_user_id.signature"/></div>'
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

    def _send(self, wizard):
        wizard.action_send_and_print()
        message = self.env["mail.message"].search(
            [("model", "=", "account.move"), ("res_id", "=", wizard.move_id.id),
             ("message_type", "=", "comment")],
            order="id desc",
            limit=1,
        )
        self.assertTrue(message)
        return message

    def _mails(self, message):
        return self.env["mail.mail"].sudo().search([("mail_message_id", "=", message.id)])

    def _check_sent_once(self, message):
        self.assertEqual(message.body.count(SENDER_TEXT), 1, message.body)
        self.assertNotIn(OTHER_TEXT, message.body)
        mails = self._mails(message)
        self.assertTrue(mails)
        for mail in mails:
            self.assertEqual(mail.body_html.count(SENDER_TEXT), 1, mail.body_html)
            self.assertNotIn(OTHER_TEXT, mail.body_html)

    def test_salesperson_not_sender(self):
        invoice = self.init_invoice("out_invoice", amounts=[100], post=True)
        invoice.invoice_user_id = self.other_user
        wizard = self._wizard(invoice)
        self.assertNotIn(OTHER_TEXT, wizard.body)
        self.assertEqual(str(wizard.body).count(SENDER_TEXT), 1, wizard.body)
        self.assertIn("o_bemade_mail_signature", wizard.body)
        self._check_sent_once(self._send(wizard))

    def test_salesperson_is_sender(self):
        invoice = self.init_invoice("out_invoice", amounts=[100], post=True)
        invoice.invoice_user_id = self.env.user
        wizard = self._wizard(invoice)
        self.assertEqual(str(wizard.body).count(SENDER_TEXT), 1, wizard.body)
        self._check_sent_once(self._send(wizard))

    def test_credit_note(self):
        refund = self.init_invoice("out_refund", amounts=[100], post=True)
        refund.invoice_user_id = self.other_user
        wizard = self._wizard(refund)
        self.assertNotIn(OTHER_TEXT, wizard.body)
        self._check_sent_once(self._send(wizard))

    def test_signature_removed_by_sender(self):
        invoice = self.init_invoice("out_invoice", amounts=[100], post=True)
        wizard = self._wizard(invoice)
        wizard.body = Markup("<p>Here is your invoice.</p>")
        message = self._send(wizard)
        self.assertNotIn(SENDER_TEXT, message.body)
        for mail in self._mails(message):
            self.assertNotIn(SENDER_TEXT, mail.body_html)
