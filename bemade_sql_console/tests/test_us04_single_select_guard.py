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
"""

import os
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import SqlConsoleTestBase

# The "not configured" message fragment for distinguishing guard vs env errors
_NOT_CONFIGURED_FRAGMENT = "not configured"
_GUARD_MULTI_FRAGMENT = "single"
_GUARD_VERB_FRAGMENT = "SELECT or WITH"


@tagged("at_install", "post_install")
class TestSingleSelectGuard(SqlConsoleTestBase):
    """US-04: Statement guard raises UserError before any connection is attempted."""

    def _assert_guard_error_not_configured(self, sql):
        """Assert that the guard (not the missing-env-var error) fires.

        With env vars unset, the "not configured" UserError would come AFTER the
        guard.  The guard must fire first, so the error message must be the
        guard's, not the "not configured" one.
        """
        saved_user = os.environ.pop("ODOO_RO_DB_USER", None)
        saved_pass = os.environ.pop("ODOO_RO_DB_PASSWORD", None)
        try:
            with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                with self.assertRaises(UserError) as cm:
                    self.env["sql.console"].run_query(sql)
            msg = str(cm.exception)
            self.assertNotIn(
                _NOT_CONFIGURED_FRAGMENT,
                msg,
                f"Guard should fire before env-var check, but got 'not configured': {msg}",
            )
        finally:
            if saved_user is not None:
                os.environ["ODOO_RO_DB_USER"] = saved_user
            if saved_pass is not None:
                os.environ["ODOO_RO_DB_PASSWORD"] = saved_pass

    def test_multi_statement_rejected(self):
        """'SELECT 1; SELECT 2' raises UserError for multiple statements."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError) as cm:
                self.env["sql.console"].run_query("SELECT 1; SELECT 2")
        self.assertIn(_GUARD_MULTI_FRAGMENT, str(cm.exception).lower())

    def test_delete_verb_rejected(self):
        """'DELETE FROM res_partner' raises UserError (non-SELECT leading verb)."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError):
                self.env["sql.console"].run_query("DELETE FROM res_partner")

    def test_update_verb_rejected(self):
        """'UPDATE …' raises UserError (non-SELECT leading verb)."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError):
                self.env["sql.console"].run_query(
                    "UPDATE res_partner SET name='x' WHERE id=1"
                )

    def test_insert_verb_rejected(self):
        """'INSERT …' raises UserError (non-SELECT leading verb)."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError):
                self.env["sql.console"].run_query(
                    "INSERT INTO res_partner (name) VALUES ('x')"
                )

    def test_set_statement_rejected(self):
        """'SET statement_timeout=0' raises UserError (SET is not SELECT/WITH)."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError):
                self.env["sql.console"].run_query("SET statement_timeout=0")

    def test_drop_verb_rejected(self):
        """'DROP TABLE …' raises UserError."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError):
                self.env["sql.console"].run_query("DROP TABLE res_partner")

    def test_guard_fires_before_env_check_multi_statement(self):
        """Guard fires before the env-var check for a multi-statement query."""
        self._assert_guard_error_not_configured("SELECT 1; SELECT 2")

    def test_guard_fires_before_env_check_delete(self):
        """Guard fires before the env-var check for DELETE verb."""
        self._assert_guard_error_not_configured("DELETE FROM res_partner")

    def test_guard_fires_before_env_check_set(self):
        """Guard fires before the env-var check for SET statement."""
        self._assert_guard_error_not_configured("SET statement_timeout=0")

    def test_no_connection_attempted_on_guard_failure(self):
        """When the guard fires, psycopg2.connect is never called."""
        import psycopg2
        with patch("psycopg2.connect") as mock_connect:
            with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                with self.assertRaises(UserError):
                    self.env["sql.console"].run_query("DELETE FROM res_partner")
            mock_connect.assert_not_called()

    def test_trailing_semicolon_allowed(self):
        """A single trailing semicolon is acceptable (common SQL habit)."""
        result = self.env["sql.console"].run_query("SELECT 42 AS v;")
        self.assertEqual(result["rows"][0][0], 42)

    def test_select_with_cte_allowed(self):
        """A non-writable CTE (WITH … SELECT) passes the guard and executes."""
        result = self.env["sql.console"].run_query(
            "WITH x AS (SELECT 1 AS n) SELECT n FROM x"
        )
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["rows"][0][0], 1)

    def test_empty_sql_rejected(self):
        """Empty or whitespace-only SQL raises UserError."""
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError):
                self.env["sql.console"].run_query("")
        with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
            with self.assertRaises(UserError):
                self.env["sql.console"].run_query("   ")
