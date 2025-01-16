from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    delivery_carrier_id = fields.Many2one(
        comodel_name="delivery.carrier",
        string="Default Carrier",
    )
