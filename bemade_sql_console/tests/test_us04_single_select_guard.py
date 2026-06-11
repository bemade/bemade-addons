"""
US-04 — Single-statement / SELECT-verb guard rejects bad input before connecting.

Acceptance criteria
-------------------
- "SELECT 1; SELECT 2" raises UserError (multi-statement).
- "DELETE FROM res_partner" raises UserError (non-SELECT verb).
- "UPDATE res_partner SET name='x' WHERE id=1" raises UserError.
- "SET statement_timeout=0" raises UserError.
- Guard fires BEFORE any connection attempt: even with env vars unset, the
  guard error (not the "not configured" error) is raised.

Phase 4: implement test body.
"""

from .common import SqlConsoleTestBase


class TestSingleSelectGuard(SqlConsoleTestBase):
    """Phase 4 implements the test body."""
