from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    activity_done_lang = fields.Selection(
        related="company_id.activity_done_lang", readonly=False
    )
