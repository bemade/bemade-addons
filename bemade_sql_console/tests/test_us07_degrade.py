"""
US-07 — Graceful degradation when RO env vars are absent.

Acceptance criteria
-------------------
- Unsetting ODOO_RO_DB_USER / ODOO_RO_DB_PASSWORD causes run_query("SELECT 1")
  to raise UserError with the "not configured" message.
- No psycopg2 connection is attempted (spy on psycopg2.connect).
- self.env.cr is not queried (spy on env.cr.execute).

Phase 4: implement test body.
"""

from .common import SqlConsoleTestBase


class TestDegrade(SqlConsoleTestBase):
    """Phase 4 implements the test body."""
