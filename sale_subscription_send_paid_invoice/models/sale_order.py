from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _subscription_post_success_payment(self, transaction, invoices, automatic=True):
        res = super()._subscription_post_success_payment(
            transaction, invoices, automatic=automatic
        )
        self._send_paid_subscription_invoices(invoices)
        return res

    def _send_paid_subscription_invoices(self, invoices):
        """Email paid invoices the way unpaid recurring invoices are emailed.

        Upstream only sends recurring invoices from the invoicing cron when the
        subscription has no payment token (``validate_and_send_invoice``); a
        successful payment only triggers a payment confirmation to the order
        contact. Send the invoice itself with the plan's template, mirroring
        ``validate_and_send_invoice`` minus its cursor commit, which has no
        place in transaction post-processing.
        """
        self.ensure_one()
        template = self.plan_id.invoice_mail_template_id
        if not template:
            return
        to_send = invoices.filtered(
            lambda move: move.state == "posted"
            and not move.is_move_sent
            and move._is_ready_to_be_sent()
        )
        for invoice in to_send:
            email_context = {
                **self.env.context,
                "total_amount": invoice.amount_total,
                "email_to": invoice.partner_id.email,
                "code": self.client_order_ref or self.name,
                "currency": invoice.currency_id.name,
            }
            self.env["account.move.send"].with_context(
                **email_context
            )._generate_and_send_invoices(
                invoice,
                allow_raising=False,
                allow_fallback_pdf=True,
                mail_template=template,
            )
