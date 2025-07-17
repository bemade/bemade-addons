from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    openwebui_provider_id = fields.Many2one(
        comodel_name="openwebui.provider",
        related="company_id.openwebui_provider_id",
        readonly=False,
        company_dependent=True,
    )

    openwebui_default_model_id = fields.Many2one(
        comodel_name="openwebui.model",
        related="company_id.openwebui_default_model_id",
        readonly=False,
        company_dependent=True,
    )
