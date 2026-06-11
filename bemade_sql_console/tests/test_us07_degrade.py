"""
US-07 — Graceful degradation when RO env vars are absent.

Acceptance criteria
-------------------
- Unsetting ODOO_RO_DB_USER / ODOO_RO_DB_PASSWORD causes run_query("SELECT 1")
  to raise UserError with the "not configured" message.
- No psycopg2 connection is attempted (spy on psycopg2.connect).
- self.env.cr is not queried (spy on env.cr.execute).

Note: this test class does NOT inherit the RO-role setup from SqlConsoleTestBase
for the purpose of env-var removal tests.  The base class's setUpClass populates
the env vars; each test method here temporarily removes them.
"""

import os
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import SqlConsoleTestBase

_NOT_CONFIGURED_MSG = "not configured"


@tagged("at_install", "post_install")
class TestDegrade(SqlConsoleTestBase):
    """US-07: Missing env vars produce a clean UserError with no fallback."""

    def _unset_env(self):
        """Remove the RO env vars and return their original values."""
        saved = {
            "ODOO_RO_DB_USER": os.environ.pop("ODOO_RO_DB_USER", None),
            "ODOO_RO_DB_PASSWORD": os.environ.pop("ODOO_RO_DB_PASSWORD", None),
        }
        return saved

    def _restore_env(self, saved):
        """Restore the env vars from the saved dict."""
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def test_missing_both_vars_raises_user_error(self):
        """When both env vars are absent, UserError with 'not configured' is raised."""
        saved = self._unset_env()
        try:
            with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                with self.assertRaises(UserError) as cm:
                    self.env["sql.console"].run_query("SELECT 1")
            self.assertIn(
                _NOT_CONFIGURED_MSG,
                str(cm.exception),
                f"Expected 'not configured' in error, got: {cm.exception}",
            )
        finally:
            self._restore_env(saved)

    def test_missing_user_only_raises_user_error(self):
        """When only ODOO_RO_DB_USER is absent, UserError is raised."""
        saved_user = os.environ.pop("ODOO_RO_DB_USER", None)
        try:
            with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                with self.assertRaises(UserError) as cm:
                    self.env["sql.console"].run_query("SELECT 1")
            self.assertIn(_NOT_CONFIGURED_MSG, str(cm.exception))
        finally:
            if saved_user is not None:
                os.environ["ODOO_RO_DB_USER"] = saved_user

    def test_missing_password_only_raises_user_error(self):
        """When only ODOO_RO_DB_PASSWORD is absent, UserError is raised."""
        saved_pass = os.environ.pop("ODOO_RO_DB_PASSWORD", None)
        try:
            with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                with self.assertRaises(UserError) as cm:
                    self.env["sql.console"].run_query("SELECT 1")
            self.assertIn(_NOT_CONFIGURED_MSG, str(cm.exception))
        finally:
            if saved_pass is not None:
                os.environ["ODOO_RO_DB_PASSWORD"] = saved_pass

    def test_no_psycopg2_connect_attempted(self):
        """psycopg2.connect is never called when env vars are missing."""
        saved = self._unset_env()
        try:
            with patch("psycopg2.connect") as mock_connect:
                with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                    with self.assertRaises(UserError):
                        self.env["sql.console"].run_query("SELECT 1")
                mock_connect.assert_not_called()
        finally:
            self._restore_env(saved)

    def test_no_owner_cr_query_attempted(self):
        """env.cr.execute is not called with the user's SQL when env vars are missing.

        (env.cr may be used by Odoo internals like ir.config_parameter.get_param,
        but the user's SELECT 1 must not appear in those calls.)
        """
        saved = self._unset_env()
        try:
            real_execute = self.env.cr.execute
            call_sqls = []

            def spy_execute(sql, *args, **kwargs):
                call_sqls.append(str(sql)[:200])
                return real_execute(sql, *args, **kwargs)

            with patch.object(self.env.cr, "execute", side_effect=spy_execute):
                with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                    with self.assertRaises(UserError):
                        self.env["sql.console"].run_query(
                            "SELECT 999 AS sentinel_us07"
                        )

            matched = [s for s in call_sqls if "sentinel_us07" in s]
            self.assertFalse(
                matched,
                f"User SQL appeared in env.cr calls despite env vars being absent: {matched}",
            )
        finally:
            self._restore_env(saved)

    def test_empty_string_env_vars_raise_user_error(self):
        """Empty string env vars (not unset but blank) also trigger the error."""
        saved = {
            "ODOO_RO_DB_USER": os.environ.get("ODOO_RO_DB_USER"),
            "ODOO_RO_DB_PASSWORD": os.environ.get("ODOO_RO_DB_PASSWORD"),
        }
        os.environ["ODOO_RO_DB_USER"] = "  "   # whitespace only
        os.environ["ODOO_RO_DB_PASSWORD"] = ""
        try:
            with mute_logger("odoo.addons.bemade_sql_console.models.sql_console"):
                with self.assertRaises(UserError) as cm:
                    self.env["sql.console"].run_query("SELECT 1")
            self.assertIn(_NOT_CONFIGURED_MSG, str(cm.exception))
        finally:
            for key, val in saved.items():
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val
