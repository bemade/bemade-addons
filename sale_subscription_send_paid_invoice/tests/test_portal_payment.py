"""Use case: the customer pays a subscription on the portal.

Acceptance criteria:
- After the portal payment succeeds, the invoice it creates is emailed with
  the plan's invoice email template to the invoice address.
- The invoice is marked as sent.
"""

from odoo.tests import tagged

from .common import SendPaidInvoiceCommon


@tagged("post_install", "-at_install")
class TestPortalPayment(SendPaidInvoiceCommon):
    def test_portal_paid_invoice_is_emailed_to_invoice_address(self):
        invoice = self._pay_on_portal()

        self.assertEqual(len(invoice), 1)
        self.assertEqual(invoice.state, "posted")
        self.assertTrue(invoice.is_move_sent)
        self.assertEqual(len(self._invoice_emails_to(invoice, self.ap_contact)), 1)
