"""
US-01 — Valid SELECT returns correct JSON envelope shape and coerced types.

Acceptance criteria
-------------------
- run_query("SELECT 1 AS a, now() AS t, 1.5::numeric AS n") returns a dict
  with keys columns, rows, row_count, truncated.
- Every value in the envelope is JSON-serializable (json.dumps succeeds).
- Decimal values are returned as str (not float).
- datetime values are returned as ISO-8601 strings.

Phase 4: implement test body.
"""

from .common import SqlConsoleTestBase


class TestEnvelope(SqlConsoleTestBase):
    """Phase 4 implements the test body."""
