"""
US-06 — Row cap and truncated flag.

Acceptance criteria
-------------------
- Set bemade_sql_console.row_cap = 2 in ir.config_parameter.
- SELECT generate_series(1,5) → row_count == 2, len(rows) == 2, truncated is True.
- SELECT generate_series(1,2) → truncated is False.

Phase 4: implement test body.
"""

from .common import SqlConsoleTestBase


class TestRowCap(SqlConsoleTestBase):
    """Phase 4 implements the test body."""
