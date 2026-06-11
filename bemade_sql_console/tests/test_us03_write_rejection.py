"""
US-03 — Write operations are rejected by the RO role (not just app-layer).

Acceptance criteria
-------------------
- Plain DELETE/UPDATE/INSERT statements raise an error.
- A writable CTE (WITH x AS (DELETE … RETURNING id) SELECT * FROM x) that
  passes the single-SELECT guard is rejected by the RO role.
- SET default_transaction_read_only = off / SET TRANSACTION READ WRITE raise.
- Embedded COMMIT raises (multi-statement, caught by guard before role).
- Post-condition: no rows were modified (verify against scratch data).

Requires a live SELECT-only Postgres role (see common.py).  Degrades to
app-layer-only coverage when CREATEROLE is unavailable on the test runner.

Phase 4: implement test body.
"""

from .common import SqlConsoleTestBase


class TestWriteRejection(SqlConsoleTestBase):
    """Phase 4 implements the test body."""
