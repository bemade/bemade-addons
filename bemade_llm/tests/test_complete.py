"""Use case: a module gets validated JSON from a stream.

Acceptance criteria
- ``env["bemade.llm.stream"].get(code).complete(system, data, schema)``
  POSTs once to ``<base_url>/chat/completions`` (no double slash) with the
  stream's model, temperature and max tokens, and returns the parsed object.
- The system prompt carries the caller's instructions plus a JSON
  instruction; the data goes in the user message, between delimiters.
- In ``json_schema`` mode the request carries ``response_format`` with the
  schema; in ``prompt`` mode it carries none.
- When the server ignores ``response_format`` and wraps the JSON in a code
  fence or in prose, the object is still extracted and validated.
- When the server rejects ``response_format`` (HTTP 400), the call is retried
  once without it.
- Without a schema, ``complete()`` returns the raw text.
"""

from odoo.tests import tagged

from .common import PERSON_SCHEMA, FakeResponse, LlmCase

ANSWER = {"first": "Ada", "last": "Example", "method": "signature"}


@tagged("post_install", "-at_install")
class TestComplete(LlmCase):
    def test_happy_path(self):
        self.stream.write({"temperature": 0.2, "max_tokens": 300})
        with self.mock_post(self.ok(ANSWER)) as calls:
            result = self.Stream.get("test_stream").complete(
                "Find the person.", "Regards,\nAda Example", PERSON_SCHEMA
            )
        self.assertEqual(result, ANSWER)
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["url"], "http://llm.invalid/v1/chat/completions")
        body = call["json"]
        self.assertEqual(body["model"], "tiny-model")
        self.assertEqual(body["temperature"], 0.2)
        self.assertEqual(body["max_tokens"], 300)
        system, user = body["messages"]
        self.assertEqual(system["role"], "system")
        self.assertIn("Find the person.", system["content"])
        self.assertIn("JSON", system["content"])
        self.assertEqual(user["role"], "user")
        self.assertIn("<data>\nRegards,\nAda Example\n</data>", user["content"])
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertEqual(body["response_format"]["json_schema"]["schema"], PERSON_SCHEMA)
        self.assertNotIn("Authorization", call["headers"])
        self.assertEqual(call["timeout"], self.local.timeout)

    def test_prompt_mode_sends_no_response_format(self):
        self.local.structured_output = "prompt"
        with self.mock_post(self.ok(ANSWER)) as calls:
            self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertNotIn("response_format", calls[0]["json"])

    def test_json_object_mode(self):
        self.local.structured_output = "json_object"
        with self.mock_post(self.ok(ANSWER)) as calls:
            self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertEqual(calls[0]["json"]["response_format"], {"type": "json_object"})

    def test_fenced_output_when_response_format_ignored(self):
        fenced = "Sure! Here it is:\n```json\n" + '{"first": "Ada", "last": "Example", "method": "signature"}' + "\n```"
        with self.mock_post(self.ok(fenced)):
            result = self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertEqual(result, ANSWER)

    def test_prose_wrapped_output(self):
        prose = 'The answer is {"first": "Ada", "last": "Example", "method": "signature"} as asked.'
        with self.mock_post(self.ok(prose)):
            result = self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertEqual(result, ANSWER)

    def test_retry_without_response_format_on_400(self):
        refused = FakeResponse(400, {"error": {"message": "response_format not supported"}})
        with self.mock_post(refused, self.ok(ANSWER)) as calls:
            result = self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertEqual(result, ANSWER)
        self.assertEqual(len(calls), 2)
        self.assertIn("response_format", calls[0]["json"])
        self.assertNotIn("response_format", calls[1]["json"])

    def test_without_schema_returns_text(self):
        with self.mock_post(self.ok("plain words")) as calls:
            result = self.stream.complete("Say something.", "x")
        self.assertEqual(result, "plain words")
        self.assertNotIn("response_format", calls[0]["json"])

    def test_extra_headers_sent(self):
        self.local.extra_headers = '{"X-Title": "Odoo"}'
        with self.mock_post(self.ok(ANSWER)) as calls:
            self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertEqual(calls[0]["headers"]["X-Title"], "Odoo")
