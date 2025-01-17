from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    purchase_delivery_carrier_id = fields.Many2one(
        comodel_name="delivery.carrier",
        string="Default Carrier (Inbound)",
    )

    purchase_delivery_carrier_account_id = fields.Many2one(
        comodel_name="delivery.carrier.account",
        string="Default Carrier Account (Inbound)",
    )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for partner in res:
            if (
                partner.purchase_delivery_carrier_account_id
                and not partner.purchase_delivery_carrier_id
            ):
                partner.purchase_delivery_carrier_id = (
                    partner.purchase_delivery_carrier_account_id.delivery_carrier_id
                )
        return res

    def write(self, vals):
        res = super().write(vals)
        for partner in self:
            if (
                partner.purchase_delivery_carrier_account_id
                and not partner.purchase_delivery_carrier_id
            ):
                partner.purchase_delivery_carrier_id = (
                    partner.purchase_delivery_carrier_account_id.delivery_carrier_id
                )
        return res
