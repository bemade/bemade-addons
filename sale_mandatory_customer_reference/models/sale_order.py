from odoo import models, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_enforce_customer_reference(self):
        """Get the configuration parameter for customer reference enforcement."""
        return self.env['ir.config_parameter'].sudo().get_param(
            'sale_mandatory_customer_reference.enforce_customer_reference', False)

    def action_confirm(self):
        """Override to check for customer reference before confirmation."""
        for order in self:
            if order._get_enforce_customer_reference():
                # For online payments with successful transactions, set reference to "Credit Card" if not set
                successful_tx = order.transaction_ids.filtered(lambda tx: tx.state == 'done')
                if successful_tx and not order.client_order_ref:
                    order.client_order_ref = "Credit Card"
                elif not order.client_order_ref:
                    raise ValidationError(
                        order._get_missing_customer_reference_message()
                    )
        return super().action_confirm()

    def _portal_reference_missing(self):
        """True when the portal must not let the customer sign yet.

        Mirrors the guard in the portal accept controller: enforcement on,
        no reference, and the order is not going through payment (a paid
        order is confirmed after payment, where the reference falls back to
        "Credit Card").
        """
        self.ensure_one()
        return bool(
            self._get_enforce_customer_reference()
            and not self.client_order_ref
            and self._has_to_be_signed()
            and not self._has_to_be_paid()
        )

    def _get_missing_customer_reference_message(self):
        return _(
            "Customer reference (PO Number) is required before confirming this order. "
            "Please set the customer reference field."
        )
