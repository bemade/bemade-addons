"""
US-02 — run_query never uses self.env.cr for the query.

Acceptance criteria
-------------------
- self.env.cr.execute is NOT called during run_query.
- The query runs on a connection with a different backend_pid than self.env.cr.
"""

from unittest.mock import patch

from odoo.tests import tagged

from .common import SqlConsoleTestBase


@tagged("at_install", "post_install")
class TestNoOwnerCursor(SqlConsoleTestBase):
    """US-02: run_query must never touch self.env.cr to run the user's query."""

    def test_cr_execute_not_called_during_query(self):
        """Spy on env.cr.execute to ensure it is not used for the SQL query.

        We patch env.cr.execute and assert it is NOT called during run_query.
        (env.cr may still be called by Odoo internals *outside* our code path,
        but the patch wraps it so we can detect any calls within run_query itself.)
        """
        real_execute = self.env.cr.execute
        call_sqls = []

        def spy_execute(sql, *args, **kwargs):
            call_sqls.append(str(sql)[:200])
            return real_execute(sql, *args, **kwargs)

        with patch.object(self.env.cr, "execute", side_effect=spy_execute):
            # Run a distinctive query that would appear in call_sqls if the
            # owner cursor were used
            result = self.env["sql.console"].run_query(
                "SELECT 42 AS sentinel_value_us02"
            )

        # The query itself must not appear in calls on env.cr
        matched = [s for s in call_sqls if "sentinel_value_us02" in s]
        self.assertFalse(
            matched,
            f"User SQL was executed on env.cr (owner connection): {matched}",
        )
        # But the result is correct (proving it ran somewhere)
        self.assertEqual(result["rows"][0][0], 42)

    def test_different_backend_pid(self):
        """The RO connection reports a different backend_pid than env.cr.

        env.cr's pid is retrieved via pg_backend_pid() on the owner connection.
        The RO connection pid must differ, confirming separate connections.
        """
        # Get env.cr's backend pid
        self.env.cr.execute("SELECT pg_backend_pid()")
        owner_pid = self.env.cr.fetchone()[0]

        # run_query returns a different backend_pid via the RO connection
        result = self.env["sql.console"].run_query("SELECT pg_backend_pid() AS pid")
        ro_pid = result["rows"][0][0]

        self.assertIsNotNone(ro_pid)
        self.assertNotEqual(
            int(ro_pid),
            owner_pid,
            "RO connection must use a different backend process than env.cr",
        )
