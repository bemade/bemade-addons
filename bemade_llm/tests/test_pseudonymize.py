"""Use case: a pseudonymizer can hide values from the model.

Acceptance criteria
- With the default ``none`` pseudonymizer the data is sent unchanged.
- An extension that replaces values by placeholders in ``_pseudonymize``
  gets them sent as placeholders; ``_restore`` puts the originals back in
  every string of the validated result (nested dicts and lists included).
"""

from unittest.mock import patch

from odoo.tests import tagged

from .common import LlmCase

SCHEMA = {
    "type": "object",
    "properties": {
        "who": {"type": "string"},
        "notes": {"type": "array", "items": {"type": "string"}},
        "nested": {"type": "object", "properties": {"x": {"type": "string"}}},
    },
    "required": ["who"],
}


def fake_pseudonymize(self, text):
    mapping = {"PERSON_1": "Ada Example", "ORG_1": "Example Labs"}
    for placeholder, original in mapping.items():
        text = text.replace(original, placeholder)
    return text, mapping


@tagged("post_install", "-at_install")
class TestPseudonymize(LlmCase):
    def test_none_sends_data_unchanged(self):
        with self.mock_post(self.ok({"who": "x"})) as calls:
            self.stream.complete("Who?", "Ada Example of Example Labs", SCHEMA)
        self.assertIn("Ada Example of Example Labs", calls[0]["json"]["messages"][1]["content"])

    def test_round_trip(self):
        answer = {"who": "PERSON_1", "notes": ["works at ORG_1"], "nested": {"x": "PERSON_1!"}}
        Stream = type(self.stream)
        with patch.object(Stream, "_pseudonymize", fake_pseudonymize, create=True):
            with self.mock_post(self.ok(answer)) as calls:
                result = self.stream.complete("Who?", "Ada Example of Example Labs", SCHEMA)
        sent = calls[0]["json"]["messages"][1]["content"]
        self.assertIn("PERSON_1 of ORG_1", sent)
        self.assertNotIn("Ada", sent)
        self.assertEqual(
            result,
            {"who": "Ada Example", "notes": ["works at Example Labs"], "nested": {"x": "Ada Example!"}},
        )
