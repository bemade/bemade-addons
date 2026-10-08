from unittest.mock import patch

from odoo.addons.mail.tests.common import MockEmail
from odoo.addons.payment.tests.common import PaymentCommon
from odoo.addons.sale_subscription.tests.common_sale_subscription import (
    TestSubscriptionCommon,
)

DO_PAYMENT = "odoo.addons.sale_subscription.models.sale_order.SaleOrder._do_payment"


class SendPaidInvoiceCommon(PaymentCommon, TestSubscriptionCommon, MockEmail):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The invoice address is a separate accounts-payable contact, as on a
        # real customer: the invoice must reach it, not the order contact.
        cls.ap_contact = cls.env["res.partner"].create(
            {
                "name": "Accounts Payable",
                "type": "invoice",
                "parent_id": cls.partner.id,
                "email": "payables@fleetwood.mac",
            }
        )
        cls.subscription.write(
            {
                "partner_id": cls.partner.id,
                "partner_invoice_id": cls.ap_contact.id,
                "company_id": cls.company.id,
            }
        )

    def _run_cron_with_token(self):
        """Confirm the subscription with a saved card and let the recurring
        invoicing cron charge it successfully."""
        self.subscription.payment_token_id = self.payment_token
        self.subscription.action_confirm()
        with patch(DO_PAYMENT, wraps=self._mock_subscription_do_payment):
            self.env["sale.order"]._cron_recurring_create_invoice()
            self.subscription.transaction_ids._post_process()
        return self.subscription.invoice_ids.sorted("id")[-1:]

    def _pay_on_portal(self):
        """Confirm the subscription and record a successful payment made by
        the customer on the portal (no saved card)."""
        self.subscription.action_confirm()
        tx = self.env["payment.transaction"].create(
            {
                "amount": self.subscription.amount_total,
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method_id,
                "operation": "online_direct",
                "currency_id": self.subscription.currency_id.id,
                "reference": "PORTAL-PAYMENT",
                "partner_id": self.partner.id,
                "sale_order_ids": [(6, 0, self.subscription.ids)],
                "subscription_action": "manual_send_mail",
                "state": "done",
            }
        )
        tx._post_process()
        return tx.invoice_ids

    def _invoice_emails_to(self, invoice, partner):
        """Invoice emails posted on the invoice and addressed to partner."""
        return self.env["mail.message"].search(
            [
                ("model", "=", "account.move"),
                ("res_id", "=", invoice.id),
                ("message_type", "in", ("comment", "email_outgoing")),
                ("partner_ids", "in", partner.ids),
            ]
        )
