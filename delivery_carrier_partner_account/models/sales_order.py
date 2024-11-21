from odoo import models, fields, api, _


class SalesOrder(models.Model):
    _inherit = ["sale.order", "carrier.account.mixin"]
    _name = "sale.order"

    recipient_id = fields.Many2one(
        comodel_name="res.partner",
        related="partner_id",
    )
    sender_id = fields.Many2one(
        comodel_name="res.partner",
        related="company_id.partner_id",
    )

    @api.model
    def write(self, values):
        res = super().write(values)
        # If carrier account ID changes for a confirmed order, change it on its
        # pending pickings as well.
        if "carrier_account_id" in values:
            for rec in self.filtered(
                lambda order: order.state not in ["draft", "sent"]
            ):
                for picking in rec.picking_ids.filtered(
                    lambda pick: pick.state not in ("done", "cancel")
                ):
                    picking.carrier_account_id = rec.carrier_account_id
        return res
