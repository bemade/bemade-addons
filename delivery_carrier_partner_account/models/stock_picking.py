from odoo import models, fields, api


class Picking(models.Model):
    _inherit = ["stock.picking", "carrier.account.mixin"]
    _name = "stock.picking"

    recipient_id = fields.Many2one(
        comodel_name="res.partner",
        related="partner_id",
    )
    sender_id = fields.Many2one(
        comodel_name="res.partner",
        related="company_id.partner_id",
    )

    # Override to base it on the sale order field initially and when changed
    delivery_billing_mode = fields.Selection(
        compute="_compute_delivery_billing_mode",
        inverse="_inverse_delivery_billing_mode",
        store=True,
    )

    @api.depends("sale_id", "sale_id.delivery_billing_mode")
    def _compute_delivery_billing_mode(self):
        for rec in self:
            rec.delivery_billing_mode = rec.sale_id.delivery_billing_mode
            rec.carrier_account_id = rec.sale_id.carrier_account_id

    def _inverse_delivery_billing_mode(self):
        pass
