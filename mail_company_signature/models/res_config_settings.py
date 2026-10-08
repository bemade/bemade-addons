from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_signature_enforced = fields.Boolean(
        related="company_id.company_signature_enforced", readonly=False
    )
    company_signature_template = fields.Html(
        related="company_id.company_signature_template", readonly=False
    )
