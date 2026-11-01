"""Use case: the recurring invoicing cron charges a saved card.

Acceptance criteria:
- After the automatic card charge succeeds, the recurring invoice is posted
  and emailed with the plan's invoice email template.
- The email is addressed to the subscription's invoice address (the
  accounts-payable contact), not only to the order contact.
- The invoice is marked as sent.
"""

from odoo.tests import tagged

from .common import SendPaidInvoiceCommon


@tagged("post_install", "-at_install")
class TestCronTokenPayment(SendPaidInvoiceCommon):
    def test_card_charged_invoice_is_emailed_to_invoice_address(self):
        invoice = self._run_cron_with_token()

        self.assertEqual(invoice.state, "posted")
        self.assertTrue(invoice.is_move_sent)
        self.assertEqual(len(self._invoice_emails_to(invoice, self.ap_contact)), 1)
