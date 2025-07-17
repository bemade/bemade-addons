from odoo import models, fields, api


class OpenWebUIModel(models.Model):
    _name = "openwebui.model"
    _description = "OpenWebUI Model"

    technical_name = fields.Char(
        required=True,
        help="Technical name of the model on the OpenWebUI server.",
        readonly=True,
    )
    name = fields.Char(
        required=True,
        help="User-friendly name of the model.",
        readonly=True,
    )
    provider_id = fields.Many2one(
        "openwebui.provider",
        required=True,
    )

    _sql_constraints = [
        (
            "technical_name_provider_unique",
            "unique(technical_name, provider_id)",
            "Technical name must be unique per provider",
        )
    ]
