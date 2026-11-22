"""Use case: every call leaves a content-free trace.

Acceptance criteria
- A successful call writes one ``ir.logging`` line (name ``bemade_llm``)
  carrying the stream code, provider, model, status ``ok``, latency and the
  token counts.
- A refused, failed or invalid call writes a line with its status.
- The line never contains the system prompt, the data or the answer.
"""

from odoo.tests import tagged

from odoo.addons.bemade_llm.exceptions import BemadeLlmError

from .common import PERSON_SCHEMA, LlmCase

SECRET_SYSTEM = "Find the person named Zorblax."
SECRET_DATA = "Kind regards, Quillon Vexmoor"
SECRET_ANSWER = {"first": "Quillon", "last": "Vexmoor", "method": "signature"}


@tagged("post_install", "-at_install")
class TestLogging(LlmCase):
    def logs(self):
        return self.env["ir.logging"].sudo().search(
            [("name", "=", "bemade_llm"), ("message", "ilike", "test_stream")]
        )

    def call_failing(self):
        # not assertRaises: Odoo's rolls back a savepoint, taking the log line
        try:
            self.stream.complete(SECRET_SYSTEM, SECRET_DATA, PERSON_SCHEMA)
        except BemadeLlmError:
            return
        self.fail("BemadeLlmError not raised")

    def assert_clean(self, log):
        for secret in ("Zorblax", "Quillon", "Vexmoor", "Kind regards"):
            self.assertNotIn(secret, log.message)

    def test_success_logged_without_content(self):
        with self.mock_post(self.ok(SECRET_ANSWER, prompt_tokens=42, completion_tokens=9)):
            self.stream.complete(SECRET_SYSTEM, SECRET_DATA, PERSON_SCHEMA)
        log = self.logs()
        self.assertEqual(len(log), 1)
        self.assertIn("status=ok", log.message)
        self.assertIn("provider=local_test", log.message)
        self.assertIn("model=tiny-model", log.message)
        self.assertIn("prompt_tokens=42", log.message)
        self.assertIn("completion_tokens=9", log.message)
        self.assertIn("latency_ms=", log.message)
        self.assert_clean(log)

    def test_failures_logged(self):
        cases = [
            ("invalid_output", lambda: self.mock_post(self.ok("Quillon Vexmoor, no JSON"))),
            ("transport_error", lambda: self.mock_post(self.ok({}), exc=self.TransportError("x"))),
        ]
        for status, ctx in cases:
            with self.subTest(status=status), ctx():
                self.call_failing()
        messages = self.logs().mapped("message")
        self.assertTrue(any("status=invalid_output" in m for m in messages))
        self.assertTrue(any("status=transport_error" in m for m in messages))
        for log in self.logs():
            self.assert_clean(log)

    def test_cloud_refused_logged(self):
        self.stream.provider_id = self.cloud
        with self.mock_post(self.ok({})):
            self.call_failing()
        self.assertIn("status=cloud_refused", self.logs().message)
