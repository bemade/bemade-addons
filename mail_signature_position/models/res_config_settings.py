from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mail_signature_position = fields.Selection(
        related="company_id.mail_signature_position",
        readonly=False,
    )
