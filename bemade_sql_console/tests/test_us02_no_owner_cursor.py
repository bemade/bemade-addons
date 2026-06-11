"""
US-02 — run_query never uses self.env.cr for the query.

Acceptance criteria
-------------------
- self.env.cr.execute is NOT called during run_query.
- The query runs on a connection with a different backend_pid than self.env.cr.

Phase 4: implement test body (spy on env.cr.execute via unittest.mock.patch.object).
"""

from .common import SqlConsoleTestBase


class TestNoOwnerCursor(SqlConsoleTestBase):
    """Phase 4 implements the test body."""
