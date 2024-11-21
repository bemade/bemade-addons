from odoo import models, fields, api


class DeliveryCarrierAccount(models.Model):
    _name = "delivery.carrier.account"
    _description = "Delivery Carrier Account"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    delivery_carrier_id = fields.Many2one(
        comodel_name="delivery.carrier",
        string="Delivery Carriers",
        required=True,
        ondelete="restrict",
    )

    account_number = fields.Char(
        required=True,
        tracking=1,
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        ondelete="cascade",
    )

    @api.depends("account_number")
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.account_number
