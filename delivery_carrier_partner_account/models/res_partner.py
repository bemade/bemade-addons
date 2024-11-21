from odoo import models, fields


class Partner(models.Model):
    _inherit = "res.partner"

    carrier_account_ids = fields.One2many(
        comodel_name="delivery.carrier.account",
        inverse_name="partner_id",
        tracking=2,
        string="Carrier Accounts",
    )

    default_carrier_account_id = fields.Many2one(
        comodel_name="delivery.carrier.account",
        tracking=1,
        ondelete="restrict",
    )
