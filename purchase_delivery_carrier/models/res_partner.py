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
