"""
US-01 — Valid SELECT returns correct JSON envelope shape and coerced types.

Acceptance criteria
-------------------
- run_query("SELECT 1 AS a, now() AS t, 1.5::numeric AS n") returns a dict
  with keys columns, rows, row_count, truncated.
- Every value in the envelope is JSON-serializable (json.dumps succeeds).
- Decimal values are returned as str (not float) — locked per task spec.
- datetime values are returned as ISO-8601 strings.
"""

import json

from odoo.tests import tagged

from .common import SqlConsoleTestBase


@tagged("at_install", "post_install")
class TestEnvelope(SqlConsoleTestBase):
    """US-01: Valid SELECT returns a correct, JSON-serializable envelope."""

    def test_envelope_shape_and_types(self):
        """run_query returns the expected envelope structure and coerced values."""
        sql = "SELECT 1 AS a, now() AS t, 1.5::numeric AS n"
        result = self.env["sql.console"].run_query(sql)

        # Envelope keys
        self.assertIn("columns", result)
        self.assertIn("rows", result)
        self.assertIn("row_count", result)
        self.assertIn("truncated", result)

        # Column order and names
        self.assertEqual(result["columns"], ["a", "t", "n"])

        # One row
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(len(result["rows"]), 1)
        self.assertFalse(result["truncated"])

        row = result["rows"][0]
        a_val, t_val, n_val = row

        # a == 1 (integer passthrough)
        self.assertEqual(a_val, 1)

        # t is an ISO-8601 string (datetime coerced)
        self.assertIsInstance(t_val, str, "datetime should be coerced to ISO-8601 string")
        # Simple check: contains a 'T' separator (ISO-8601 datetime)
        self.assertIn("T", t_val, "ISO-8601 datetime string should contain 'T'")

        # n is a string, not a float (Decimal → str, LOCKED)
        self.assertIsInstance(n_val, str, "Decimal should be coerced to str, not float")
        self.assertEqual(n_val, "1.5")

        # Entire envelope must be JSON-serializable (no non-serializable types)
        serialized = json.dumps(result)
        self.assertIsInstance(serialized, str)

    def test_envelope_with_various_types(self):
        """Coercion covers multiple types: bytea, uuid, bool, null."""
        sql = (
            "SELECT "
            "  TRUE AS b, "
            "  NULL::text AS n, "
            "  '\\xDEAD'::bytea AS raw, "
            "  gen_random_uuid() AS uid"
        )
        result = self.env["sql.console"].run_query(sql)
        self.assertEqual(result["row_count"], 1)
        row = result["rows"][0]
        b_val, n_val, raw_val, uid_val = row

        self.assertIs(b_val, True)
        self.assertIsNone(n_val)
        # bytea → base64 string
        self.assertIsInstance(raw_val, str)
        # uuid → str, should be 36 chars (8-4-4-4-12)
        self.assertIsInstance(uid_val, str)
        self.assertEqual(len(uid_val), 36)

        # Full JSON round-trip
        json.dumps(result)
