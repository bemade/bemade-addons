import json
import logging
import os
import re

import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..exceptions import LlmTransportError

_logger = logging.getLogger(__name__)

KEY_ENV_PREFIX = "BEMADE_LLM_KEY_"


class BemadeLlmProvider(models.Model):
    _name = "bemade.llm.provider"
    _description = "LLM Provider"
    _order = "name, id"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        help="Technical code. The API key can be overridden by the environment "
        "variable BEMADE_LLM_KEY_<CODE> (code in upper case).",
    )
    active = fields.Boolean(default=True)
    base_url = fields.Char(
        string="Base URL",
        required=True,
        help="Base URL of the OpenAI-compatible API, ending with /v1 "
        "(e.g. http://localhost:11434/v1 for Ollama).",
    )
    api_key = fields.Char(
        string="API Key",
        groups="base.group_system",
        copy=False,
        help="Optional (a local Ollama needs none).",
    )
    extra_headers = fields.Text(
        help='Optional HTTP headers as a JSON object, e.g. {"HTTP-Referer": "https://example.com"}.',
    )
    timeout = fields.Integer(
        string="Timeout (s)",
        default=120,
        help="Seconds to wait for an answer.",
    )
    is_local = fields.Boolean(
        string="On our infrastructure",
        help="Tick only for a server we run ourselves: data sent to it never "
        "leaves our infrastructure. Streams that do not allow cloud providers "
        "refuse every provider without this box ticked.",
    )
    structured_output = fields.Selection(
        [
            ("json_schema", "JSON schema (response_format)"),
            ("json_object", "JSON object (response_format)"),
            ("prompt", "Instruction in the prompt only"),
        ],
        default="json_schema",
        required=True,
        help="How the answer format is requested. Every mode also adds a JSON "
        "instruction to the prompt and validates the answer.",
    )
    stream_ids = fields.One2many("bemade.llm.stream", "provider_id", string="Streams")

    _code_unique = models.Constraint("UNIQUE(code)", "The provider code must be unique.")

    @api.constrains("extra_headers")
    def _check_extra_headers(self):
        for provider in self:
            if not provider.extra_headers:
                continue
            try:
                value = json.loads(provider.extra_headers)
            except ValueError as error:
                raise ValidationError(self.env._("Extra headers must be valid JSON.")) from error
            if not isinstance(value, dict):
                raise ValidationError(self.env._("Extra headers must be a JSON object."))

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    def _get_api_key(self):
        self.ensure_one()
        env_name = KEY_ENV_PREFIX + re.sub(r"[^A-Z0-9]", "_", (self.code or "").upper())
        return os.environ.get(env_name) or self.sudo().api_key or False

    def _get_headers(self):
        self.ensure_one()
        headers = {"Content-Type": "application/json"}
        if self.extra_headers:
            headers.update(json.loads(self.extra_headers))
        key = self._get_api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _endpoint(self, path):
        self.ensure_one()
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _post_chat_completions(self, payload):
        """POST ``payload`` to ``/chat/completions`` and return the decoded body.

        :return: ``(status_code, body)``; ``body`` is the decoded JSON for a 2xx
            or 400 answer (the caller may retry a 400 without
            ``response_format``)
        :raise LlmTransportError: unreachable, timeout, other HTTP error, or a
            body that is not JSON
        """
        self.ensure_one()
        try:
            response = requests.post(
                self._endpoint("chat/completions"),
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout or 120,
            )
        except requests.RequestException as error:
            raise LlmTransportError(
                self.env._("LLM provider %(name)s unreachable: %(error)s",
                           name=self.name, error=type(error).__name__)
            ) from error
        if response.status_code == 400 or 200 <= response.status_code < 300:
            try:
                return response.status_code, response.json()
            except ValueError as error:
                raise LlmTransportError(
                    self.env._("LLM provider %(name)s answered with a body that is not JSON.",
                               name=self.name)
                ) from error
        raise LlmTransportError(
            self.env._("LLM provider %(name)s answered HTTP %(status)s.",
                       name=self.name, status=response.status_code)
        )

    def action_test_connection(self):
        """List the models the server offers (``GET /models``)."""
        self.ensure_one()
        try:
            response = requests.get(
                self._endpoint("models"), headers=self._get_headers(), timeout=min(self.timeout or 30, 30)
            )
            response.raise_for_status()
            names = [m.get("id") for m in response.json().get("data", [])]
            message = self.env._("Connected. Models: %(models)s", models=", ".join(filter(None, names)) or "-")
            kind = "success"
        except (requests.RequestException, ValueError, AttributeError) as error:
            message = self.env._("Connection failed: %(error)s", error=type(error).__name__)
            kind = "danger"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.name, "message": message, "type": kind, "sticky": False},
        }
