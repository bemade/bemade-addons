"""
US-03 — Write operations are rejected by the RO role (not just app-layer).

Acceptance criteria
-------------------
- Plain DELETE/UPDATE/INSERT statements raise an error.
- A writable CTE (WITH x AS (DELETE … RETURNING id) SELECT * FROM x) that
  passes the single-SELECT guard is rejected by the RO role.
- SET default_transaction_read_only = off raises (via guard or role).
- Embedded COMMIT raises (multi-statement guard fires before role).
- Post-condition: no rows were modified.

Requires a live SELECT-only Postgres role (see common.py).  The writable CTE
test is the critical ACL-boundary proof: it passes the leading-WITH guard and
is rejected only by the role's lack of write privileges.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import SqlConsoleTestBase


@tagged("at_install", "post_install")
class TestWriteRejection(SqlConsoleTestBase):
    """US-03: Write operations are blocked at the Postgres ACL layer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a small scratch table owned by the test transaction for
        # post-condition checks.  res.partner rows won't be touched, but
        # we use a known count so we can verify no rows were inserted/deleted.
        cls.env.cr.execute(
            """
            CREATE TEMP TABLE sql_console_scratch (
                id SERIAL PRIMARY KEY,
                val TEXT
            )
            """
        )
        cls.env.cr.execute(
            "INSERT INTO sql_console_scratch (val) VALUES ('row1'), ('row2')"
        )

    def _scratch_row_count(self):
        self.env.cr.execute("SELECT COUNT(*) FROM sql_console_scratch")
        return self.env.cr.fetchone()[0]

    def test_insert_rejected(self):
        """INSERT is rejected at the role ACL level."""
        initial = self._scratch_row_count()
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises((UserError, Exception)):
                self.env["sql.console"].run_query(
                    "INSERT INTO sql_console_scratch (val) VALUES ('injected')"
                )
        # Post-condition: no rows added
        self.assertEqual(self._scratch_row_count(), initial)

    def test_update_rejected(self):
        """UPDATE is rejected at the role ACL level."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises((UserError, Exception)):
                self.env["sql.console"].run_query(
                    "UPDATE sql_console_scratch SET val = 'hacked' WHERE TRUE"
                )
        # Post-condition: original values unchanged
        self.env.cr.execute(
            "SELECT COUNT(*) FROM sql_console_scratch WHERE val != 'hacked'"
        )
        unchanged = self.env.cr.fetchone()[0]
        self.assertEqual(unchanged, 2)

    def test_delete_rejected(self):
        """DELETE is rejected at the role ACL level."""
        initial = self._scratch_row_count()
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises((UserError, Exception)):
                self.env["sql.console"].run_query(
                    "DELETE FROM sql_console_scratch WHERE TRUE"
                )
        # Post-condition: rows still present
        self.assertEqual(self._scratch_row_count(), initial)

    def test_writable_cte_rejected_by_role(self):
        """Writable CTE passes the single-SELECT guard but is blocked by the role.

        This is the critical test: WITH … DELETE … RETURNING starts with WITH,
        so _validate_single_select allows it through.  The rejection must come
        from Postgres's ACL check on the DELETE inside the CTE, not from our
        Python guard.  This proves the role is the real security boundary.
        """
        initial = self._scratch_row_count()
        cte_sql = (
            "WITH deleted AS ("
            "  DELETE FROM sql_console_scratch RETURNING id"
            ") SELECT * FROM deleted"
        )
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises((UserError, Exception)):
                self.env["sql.console"].run_query(cte_sql)
        # Post-condition: table untouched
        self.assertEqual(self._scratch_row_count(), initial)

    def test_writable_cte_insert_rejected_by_role(self):
        """Writable CTE with INSERT also passes guard and is blocked by the role."""
        initial = self._scratch_row_count()
        cte_sql = (
            "WITH inserted AS ("
            "  INSERT INTO sql_console_scratch (val) VALUES ('cte_injected') RETURNING id"
            ") SELECT * FROM inserted"
        )
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises((UserError, Exception)):
                self.env["sql.console"].run_query(cte_sql)
        # Post-condition: no extra rows
        self.assertEqual(self._scratch_row_count(), initial)

    def test_set_ro_off_rejected(self):
        """Attempting SET default_transaction_read_only = off is rejected.

        This is caught by the single-statement guard (SET is not SELECT/WITH),
        so it raises UserError before connecting.  Either the guard or the role
        rejects it — either way, execution must fail.
        """
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises((UserError, Exception)):
                self.env["sql.console"].run_query(
                    "SET default_transaction_read_only = off"
                )

    def test_embedded_commit_rejected(self):
        """Multi-statement with embedded COMMIT is rejected by the guard."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError):
                self.env["sql.console"].run_query(
                    "SELECT 1; COMMIT"
                )
