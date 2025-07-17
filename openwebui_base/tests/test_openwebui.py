from odoo.tests import TransactionCase, Form
import os


class TestOpenWebUI(TransactionCase):
    def setUp(self):
        super().setUp()
        self.provider = self.env["openwebui.provider"].create(
            {
                "name": "Test Provider",
                "base_url": os.getenv("OPENWEBUI_BASE_URL"),
                "api_key": os.getenv("OPENWEBUI_API_KEY"),
            }
        )

    def test_sync_models(self):
        self.assertTrue(self.provider.model_ids)
        self.assertIn(
            "MS.qwen3:32b-q8_0", self.provider.model_ids.mapped("technical_name")
        )

    def test_get_client(self):
        client = self.provider.get_client()
        self.assertTrue(client)

    def test_settings(self):
        model = self.provider.model_ids.filtered(
            lambda model: model.technical_name == "MS.qwen3:32b-q8_0"
        )
        wizard = self.env["res.config.settings"].create({})
        with Form(wizard) as form:
            form.openwebui_provider_id = self.provider
            form.openwebui_default_model_id = model
        self.assertEqual(self.env.company.openwebui_provider_id, self.provider)
        self.assertEqual(self.env.company.openwebui_default_model_id, model)

    def test_openwebui_chat(self):
        model = self.provider.model_ids.filtered(
            lambda model: model.technical_name == "MS.qwen3:32b-q8_0"
        )
        self.env.company.openwebui_default_model_id = model
        self.env.company.openwebui_provider_id = self.provider
        response = self.provider.get_client().chat.completions.create(
            model=model.technical_name,
            messages=[
                {
                    "role": "user",
                    "content": "Hello, how are you?",
                }
            ],
        )
        self.assertTrue(response and response.choices)
