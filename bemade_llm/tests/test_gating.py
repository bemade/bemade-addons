"""Use case: a stream only reaches the providers it is allowed to.

Acceptance criteria
- A stream with ``allow_cloud`` unticked (the default) whose provider is not
  on our infrastructure raises ``LlmCloudRefused`` and sends nothing.
- The same stream with ``allow_cloud`` ticked sends.
- ``get()`` of an unknown or archived code raises ``LlmNotConfigured``;
  with ``raise_if_not_found=False`` it returns an empty recordset.
- A stream without provider or model, or whose provider is archived, raises
  ``LlmNotConfigured`` on ``complete()`` and sends nothing; ``_is_ready()``
  is False for it.
- The typed errors all derive from ``BemadeLlmError``.
"""

from odoo.tests import tagged

from odoo.addons.bemade_llm.exceptions import (
    BemadeLlmError,
    LlmCloudRefused,
    LlmInvalidOutput,
    LlmNotConfigured,
    LlmTransportError,
)

from .common import PERSON_SCHEMA, LlmCase

ANSWER = {"first": "Ada", "last": "Example", "method": "signature"}


@tagged("post_install", "-at_install")
class TestGating(LlmCase):
    def test_default_is_local_only(self):
        stream = self.Stream.create({"name": "New", "code": "new_stream"})
        self.assertFalse(stream.allow_cloud)

    def test_cloud_refused_before_sending(self):
        self.stream.provider_id = self.cloud
        with self.mock_post(self.ok(ANSWER)) as calls:
            with self.assertRaises(LlmCloudRefused):
                self.stream.complete("Find the person.", "secret text", PERSON_SCHEMA)
        self.assertEqual(calls, [])

    def test_cloud_allowed_when_ticked(self):
        self.stream.write({"provider_id": self.cloud.id, "allow_cloud": True})
        with self.mock_post(self.ok(ANSWER)) as calls:
            self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer sk-test-db-key")

    def test_unknown_code(self):
        with self.assertRaises(LlmNotConfigured):
            self.Stream.get("nope")
        self.assertFalse(self.Stream.get("nope", raise_if_not_found=False))

    def test_archived_stream(self):
        self.stream.active = False
        with self.assertRaises(LlmNotConfigured):
            self.Stream.get("test_stream")

    def test_not_ready(self):
        cases = [
            {"provider_id": False},
            {"model": False},
        ]
        for vals in cases:
            with self.subTest(vals=vals):
                stream = self.stream.copy({"code": f"c_{len(vals)}_{list(vals)[0]}", **vals})
                self.assertFalse(stream._is_ready())
                with self.mock_post(self.ok(ANSWER)) as calls:
                    with self.assertRaises(LlmNotConfigured):
                        stream.complete("Find the person.", "x", PERSON_SCHEMA)
                self.assertEqual(calls, [])

    def test_archived_provider(self):
        self.local.active = False
        self.assertFalse(self.stream._is_ready())
        with self.mock_post(self.ok(ANSWER)) as calls:
            with self.assertRaises(LlmNotConfigured):
                self.stream.complete("Find the person.", "x", PERSON_SCHEMA)
        self.assertEqual(calls, [])

    def test_ready(self):
        self.assertTrue(self.stream._is_ready())

    def test_error_hierarchy(self):
        for cls in (LlmNotConfigured, LlmCloudRefused, LlmTransportError, LlmInvalidOutput):
            self.assertTrue(issubclass(cls, BemadeLlmError))
