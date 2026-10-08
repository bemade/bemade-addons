"""Use case: the subscription plan has no invoice email template.

Acceptance criteria:
- When the plan's invoice email template is empty, a card-paid invoice is not
  emailed, as in standard Odoo ("leave it empty if you don't want to send
  email automatically").
"""

from odoo.tests import tagged

from .common import SendPaidInvoiceCommon


@tagged("post_install", "-at_install")
class TestPlanWithoutTemplate(SendPaidInvoiceCommon):
    def test_no_template_means_no_email(self):
        self.subscription.plan_id.invoice_mail_template_id = False

        invoice = self._run_cron_with_token()

        self.assertEqual(invoice.state, "posted")
        self.assertFalse(invoice.is_move_sent)
        self.assertFalse(self._invoice_emails_to(invoice, self.ap_contact))
