from odoo import models, fields


class ChooseDeliveryCarrier(models.TransientModel):
    """Add options to select the carrier account and billing mode."""

    _inherit = ["choose.delivery.carrier", "carrier.account.mixin"]
    _name = "choose.delivery.carrier"

    sender_id = fields.Many2one(related="company_id.partner_id")
    recipient_id = fields.Many2one(related="partner_id")

    def button_confirm(self):
        res = super(
            ChooseDeliveryCarrier,
            self.with_context(
                delivery_billing_mode=self.delivery_billing_mode,
                carrier_account=self.carrier_account_id,
            ),
        ).button_confirm()
        extra_vals = {}
        if self.delivery_billing_mode:
            extra_vals.update(delivery_billing_mode=self.delivery_billing_mode)
        if self.carrier_account_id:
            extra_vals.update(carrier_account_id=self.carrier_account_id)
        self.order_id.write(extra_vals)
        return res
