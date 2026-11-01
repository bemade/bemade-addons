"""Use case: the invoice was already sent before the payment completed.

Acceptance criteria:
- An invoice already marked as sent when the payment succeeds is not emailed
  a second time.
"""

from unittest.mock import patch

from odoo.tests import tagged

from .common import DO_PAYMENT, SendPaidInvoiceCommon


@tagged("post_install", "-at_install")
class TestAlreadySent(SendPaidInvoiceCommon):
    def test_already_sent_invoice_is_not_resent(self):
        self.subscription.payment_token_id = self.payment_token
        self.subscription.action_confirm()

        def _pay_already_sent_invoice(payment_token, invoice, auto_commit=False):
            invoice.is_move_sent = True
            return self._mock_subscription_do_payment(
                payment_token, invoice, auto_commit=auto_commit
            )

        with patch(DO_PAYMENT, wraps=_pay_already_sent_invoice):
            self.env["sale.order"]._cron_recurring_create_invoice()
            self.subscription.transaction_ids._post_process()
        invoice = self.subscription.invoice_ids.sorted("id")[-1:]

        self.assertTrue(invoice.is_move_sent)
        self.assertFalse(self._invoice_emails_to(invoice, self.ap_contact))
