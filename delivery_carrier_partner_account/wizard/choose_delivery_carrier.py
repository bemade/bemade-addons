from odoo import models, fields


class ChooseDeliveryCarrier(models.TransientModel):
    """Add options to select the carrier account and billing mode."""

    _inherit = ["choose.delivery.carrier", "carrier.account.mixin"]
    _name = "choose.delivery.carrier"

    sender_id = fields.Many2one(related="company_id.partner_id")
    recipient_id = fields.Many2one(related="partner_id")

    def button_confirm(self):
        vals = {}
        if self.delivery_billing_mode:
            vals.update(delivery_billing_mode=self.delivery_billing_mode)
        if self.carrier_account_id:
            vals.update(carrier_account_id=self.carrier_account_id)
        if self.carrier_id:
            vals.update(carrier_id=self.carrier_id.id)
        self.order_id.with_context(no_carrier_update=True).write(vals)
        res = super().button_confirm()
        return res
