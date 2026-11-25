"""Use case: API keys stay out of reach and out of copies.

Acceptance criteria
- The key stored on the provider is sent as ``Authorization: Bearer``.
- ``BEMADE_LLM_KEY_<CODE>`` (code upper-cased) overrides the stored key.
- A provider without key sends no ``Authorization`` header.
- ``api_key`` is restricted to administrators (field groups).
- ``data/neutralize.sql`` blanks every key and archives every provider that
  is not on our infrastructure; local providers stay active.
- ``extra_headers`` must be a JSON object.
"""

import os
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.modules.neutralize import get_neutralization_queries
from odoo.tests import tagged

from .common import PERSON_SCHEMA, LlmCase

ANSWER = {"first": "Ada", "last": "Example", "method": "signature"}


@tagged("post_install", "-at_install")
class TestKeysNeutralize(LlmCase):
    def setUp(self):
        super().setUp()
        self.stream.write({"provider_id": self.cloud.id, "allow_cloud": True})

    def sent_headers(self):
        with self.mock_post(self.ok(ANSWER)) as calls:
            self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        return calls[0]["headers"]

    def test_db_key(self):
        self.assertEqual(self.sent_headers()["Authorization"], "Bearer sk-test-db-key")

    def test_env_override(self):
        with patch.dict(os.environ, {"BEMADE_LLM_KEY_CLOUD_TEST": "sk-from-env"}):
            self.assertEqual(self.sent_headers()["Authorization"], "Bearer sk-from-env")

    def test_no_key(self):
        self.cloud.api_key = False
        self.assertNotIn("Authorization", self.sent_headers())

    def test_key_is_admin_only(self):
        self.assertEqual(self.Provider._fields["api_key"].groups, "base.group_system")

    def test_neutralize(self):
        queries = list(get_neutralization_queries(["bemade_llm"]))
        self.assertTrue(queries)
        for query in queries:
            self.env.cr.execute(query)
        self.env.invalidate_all()
        providers = self.Provider.with_context(active_test=False).browse(
            [self.local.id, self.cloud.id]
        )
        self.assertFalse(any(providers.mapped("api_key")))
        self.assertTrue(self.local.active)
        self.assertFalse(self.cloud.active)

    def test_extra_headers_must_be_object(self):
        for value in ("not json", "[1, 2]"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.local.extra_headers = value
