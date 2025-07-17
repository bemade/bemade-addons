from odoo import models, fields, api
from .openwebui_model import OpenWebUIModel
import openwebui_client
from typing import Optional


class OpenWebUIProvider(models.Model):
    _name = "openwebui.provider"
    _description = "OpenWebUI Provider"

    name = fields.Char(string="Name", required=True)
    base_url = fields.Char(
        string="Base URL",
        required=True,
        help="Base URL of the OpenWebUI server.",
    )
    api_key = fields.Char(
        string="API Key",
        required=True,
        help="API key for authentication.",
        groups="base.group_system",
    )
    model_ids = fields.One2many(
        comodel_name="openwebui.model",
        inverse_name="provider_id",
    )
    default_model_id = fields.Many2one(
        comodel_name="openwebui.model",
    )

    def get_client(
        self, model: Optional[OpenWebUIModel] = None
    ) -> openwebui_client.OpenWebUIClient:
        if not self.base_url or not self.api_key:
            raise ValueError("Base URL and API key are required")
        model = model or self.default_model_id
        return openwebui_client.OpenWebUIClient(
            base_url=self.base_url,
            api_key=self.api_key,
            default_model=model.technical_name if model else None,
        )

    def sync_models(self):
        client = self.get_client()
        local_models = self.model_ids
        remote_models = {model.id: model.name for model in client.models.list()}
        for model in local_models:
            if model.technical_name not in remote_models.keys():
                model.unlink()
            elif model.name != remote_models[model.technical_name]:
                model.name = remote_models[model.technical_name]
        for model_id, model_name in remote_models.items():
            if model_id not in local_models.mapped("technical_name"):
                self.env["openwebui.model"].create(
                    {
                        "name": model_name,
                        "technical_name": model_id,
                        "provider_id": self.id,
                    }
                )

    def create(self, vals_list):
        providers = super().create(vals_list)
        for provider in providers:
            provider.sync_models()
        return providers
