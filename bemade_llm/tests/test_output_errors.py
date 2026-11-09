"""Use case: bad answers and broken servers raise typed errors.

Acceptance criteria
- A non-JSON answer raises ``LlmInvalidOutput``.
- An answer that breaks the schema (missing required key, value outside the
  enum, extra key, wrong type, too long) raises ``LlmInvalidOutput``.
- An answer without choices raises ``LlmInvalidOutput``.
- An answer cut off at the token limit (``finish_reason`` = "length") that
  holds no valid JSON raises ``LlmTruncated`` (a subclass of
  ``LlmInvalidOutput``, status "truncated"); a complete JSON answer is still
  returned even when ``finish_reason`` is "length".
- A connection error, a timeout, an HTTP 5xx, an HTTP 401 and a body that is
  not JSON raise ``LlmTransportError``.
- The schema checker (``tools.schema.validate``) covers the subset we use:
  type (incl. lists of types and null), properties, required,
  additionalProperties, enum, minLength/maxLength, items, minimum/maximum.
"""

import json

import requests

from odoo.tests import BaseCase, tagged

from odoo.addons.bemade_llm.exceptions import LlmInvalidOutput, LlmTransportError, LlmTruncated
from odoo.addons.bemade_llm.tools.schema import SchemaError, validate

from .common import PERSON_SCHEMA, FakeResponse, LlmCase


@tagged("post_install", "-at_install")
class TestOutputErrors(LlmCase):
    def assert_invalid(self, content):
        with self.mock_post(self.ok(content)):
            with self.assertRaises(LlmInvalidOutput):
                self.stream.complete("Find the person.", "x", PERSON_SCHEMA)

    def test_not_json(self):
        self.assert_invalid("I could not find anybody, sorry.")

    def test_schema_mismatch(self):
        bad = [
            {"first": "Ada", "method": "signature"},
            {"first": "Ada", "last": "Example", "method": "guess"},
            {"first": "Ada", "last": "Example", "method": "signature", "extra": 1},
            {"first": 3, "last": "Example", "method": "signature"},
            {"first": "A" * 61, "last": "Example", "method": "signature"},
            ["Ada", "Example"],
        ]
        for obj in bad:
            with self.subTest(obj=obj):
                self.assert_invalid(obj)

    def test_no_choices(self):
        with self.mock_post(FakeResponse(200, {"choices": []})):
            with self.assertRaises(LlmInvalidOutput):
                self.stream.complete("Find the person.", "x", PERSON_SCHEMA)

    def test_truncated(self):
        cut = FakeResponse(200, {
            "choices": [{"message": {"role": "assistant", "content": '{"first": "Ad'},
                         "finish_reason": "length"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 512},
        })
        with self.mock_post(cut):
            with self.assertRaises(LlmTruncated) as caught:
                self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertIsInstance(caught.exception, LlmInvalidOutput)
        self.assertEqual(caught.exception.status, "truncated")
        whole = {"first": "Ada", "last": "Example", "method": "signature"}
        complete = FakeResponse(200, {
            "choices": [{"message": {"role": "assistant", "content": json.dumps(whole)},
                         "finish_reason": "length"}],
        })
        with self.mock_post(complete):
            self.assertEqual(self.stream.complete("Find the person.", "x", PERSON_SCHEMA), whole)

    def test_not_json_complete_answer_is_not_truncated(self):
        with self.mock_post(self.ok("no json here")):
            with self.assertRaises(LlmInvalidOutput) as caught:
                self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertNotIsInstance(caught.exception, LlmTruncated)

    def test_transport_errors(self):
        for exc in (requests.ConnectionError("down"), requests.Timeout("slow")):
            with self.subTest(exc=exc):
                with self.mock_post(self.ok({}), exc=exc):
                    with self.assertRaises(LlmTransportError):
                        self.stream.complete("Find the person.", "x", PERSON_SCHEMA)

    def test_http_errors(self):
        for response in (
            FakeResponse(500, text="boom"),
            FakeResponse(401, {"error": "bad key"}),
            FakeResponse(200, text="<html>proxy</html>"),
        ):
            with self.subTest(status=response.status_code):
                with self.mock_post(response):
                    with self.assertRaises(LlmTransportError):
                        self.stream.complete("Find the person.", "x", PERSON_SCHEMA)


@tagged("post_install", "-at_install")
class TestSchemaValidator(BaseCase):
    def test_accepts(self):
        schema = {
            "type": "object",
            "properties": {
                "a": {"type": ["string", "null"]},
                "n": {"type": "integer", "minimum": 0, "maximum": 5},
                "tags": {"type": "array", "items": {"type": "string", "minLength": 1}},
                "ok": {"type": "boolean"},
                "x": {"type": "number"},
            },
            "required": ["a"],
        }
        validate({"a": None, "n": 3, "tags": ["t"], "ok": True, "x": 1.5}, schema)
        validate({"a": "s", "extra": "allowed by default"}, schema)

    def test_rejects(self):
        schema = {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "minimum": 0, "maximum": 5},
                "tags": {"type": "array", "items": {"type": "string", "minLength": 1}},
                "ok": {"type": "boolean"},
            },
        }
        for obj in ({"n": 6}, {"n": -1}, {"n": True}, {"n": 1.5}, {"tags": [""]},
                    {"tags": "t"}, {"ok": 1}, "str"):
            with self.subTest(obj=obj), self.assertRaises(SchemaError):
                validate(obj, schema)
