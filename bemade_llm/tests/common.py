import json
from contextlib import contextmanager
from unittest.mock import patch

import requests

from odoo.tests import TransactionCase

POST_PATH = "odoo.addons.bemade_llm.models.bemade_llm_provider.requests.post"

PERSON_SCHEMA = {
    "type": "object",
    "properties": {
        "first": {"type": "string", "maxLength": 60},
        "last": {"type": "string", "maxLength": 60},
        "method": {"type": "string", "enum": ["signature", "none"]},
    },
    "required": ["first", "last", "method"],
    "additionalProperties": False,
}


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload or {})

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def chat_payload(content, prompt_tokens=11, completion_tokens=7):
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
    }


class LlmCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Provider = cls.env["bemade.llm.provider"]
        cls.Stream = cls.env["bemade.llm.stream"]
        cls.local = cls.Provider.create(
            {
                "name": "Local test server",
                "code": "local_test",
                "base_url": "http://llm.invalid/v1/",
                "is_local": True,
            }
        )
        cls.cloud = cls.Provider.create(
            {
                "name": "Cloud test service",
                "code": "cloud_test",
                "base_url": "https://cloud.invalid/api/v1",
                "api_key": "sk-test-db-key",
                "is_local": False,
            }
        )
        cls.stream = cls.Stream.create(
            {
                "name": "Test stream",
                "code": "test_stream",
                "provider_id": cls.local.id,
                "model": "tiny-model",
            }
        )

    @contextmanager
    def mock_post(self, *responses, exc=None):
        """Patch ``requests.post``; yield the list of recorded calls."""
        calls = []
        queue = list(responses)

        def fake_post(url, **kwargs):
            calls.append({"url": url, **kwargs})
            if exc:
                raise exc
            return queue.pop(0) if len(queue) > 1 else queue[0]

        with patch(POST_PATH, side_effect=fake_post):
            yield calls

    def ok(self, obj, **kw):
        content = obj if isinstance(obj, str) else json.dumps(obj)
        return FakeResponse(200, chat_payload(content, **kw))

    TransportError = requests.ConnectionError
