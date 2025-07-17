from odoo import models, fields


class Company(models.Model):
    _inherit = "res.company"

    openwebui_provider_id = fields.Many2one(
        "openwebui.provider",
        string="OpenWebUI Provider",
    )
    openwebui_default_model_id = fields.Many2one(
        "openwebui.model",
        string="OpenWebUI Default Model",
        domain=[("provider_id", "=", "openwebui_provider_id")],
    )
