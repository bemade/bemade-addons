"""
US-09 — CSV export (full result) + export cap + admin check.

Acceptance criteria
-------------------
- export_query_csv(sql) returns CSV bytes whose header row == columns and whose
  data rows match the query result.
- Values containing a comma, newline or double-quote are properly quoted (csv
  module quoting), surviving a round-trip through csv.reader.
- The export is bounded by bemade_sql_console.export_row_cap (NOT the small UI
  row_cap): with export_row_cap=3, a 10-row SELECT yields 3 data rows.
- The export enforces the same admin group check as run_query (AccessError for
  a non-member).
"""

import csv
import io

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.tools.misc import mute_logger

from .common import SqlConsoleTestBase


def _parse_csv(raw_bytes):
    """Decode + parse CSV bytes into a list of rows (list of str)."""
    text = raw_bytes.decode("utf-8")
    return list(csv.reader(io.StringIO(text)))


@tagged("at_install", "post_install")
class TestCsvExport(SqlConsoleTestBase):
    """US-09: export_query_csv produces correct, properly-quoted, capped CSV."""

    def _set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(key, str(value))

    def test_header_and_rows_match_result(self):
        """CSV header == columns; data rows match the SELECT output."""
        sql = "SELECT n, n * 10 AS ten FROM generate_series(1, 3) AS n ORDER BY n"
        raw = self.env["sql.console"].export_query_csv(sql)
        parsed = _parse_csv(raw)

        # Header
        self.assertEqual(parsed[0], ["n", "ten"])
        # Data rows
        self.assertEqual(parsed[1:], [["1", "10"], ["2", "20"], ["3", "30"]])

    def test_quoting_comma_newline_quote(self):
        """Values with comma/newline/quote survive a CSV round-trip intact."""
        # Build a single-row, single-column result whose value contains all
        # three CSV-hostile characters.
        nasty = 'a,b\nc"d'
        # Use a parameterised-style literal embedded safely via dollar quoting.
        sql = "SELECT $tag$%s$tag$ AS v" % nasty
        raw = self.env["sql.console"].export_query_csv(sql)
        parsed = _parse_csv(raw)

        self.assertEqual(parsed[0], ["v"])
        # The parsed value must exactly equal the original (proves quoting worked)
        self.assertEqual(parsed[1], [nasty])

    def test_export_respects_export_cap(self):
        """export_query_csv is bounded by export_row_cap, not row_cap."""
        # Tiny UI cap, slightly larger export cap — proves they're independent.
        self._set_param("bemade_sql_console.row_cap", 1)
        self._set_param("bemade_sql_console.export_row_cap", 3)
        try:
            sql = "SELECT n FROM generate_series(1, 10) AS n ORDER BY n"
            raw = self.env["sql.console"].export_query_csv(sql)
            parsed = _parse_csv(raw)
            # 1 header + 3 data rows (export cap), NOT 1 (ui cap) or 10 (uncapped)
            self.assertEqual(len(parsed) - 1, 3, "Export must honor export_row_cap")
            self.assertEqual([r[0] for r in parsed[1:]], ["1", "2", "3"])
        finally:
            self._set_param("bemade_sql_console.row_cap", 1000)
            self._set_param("bemade_sql_console.export_row_cap", 100000)

    def test_export_default_cap_when_param_absent(self):
        """When export_row_cap is unset, a small result is fully exported."""
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .search([("key", "=", "bemade_sql_console.export_row_cap")])
        )
        saved = param.value if param else None
        if param:
            param.unlink()
        try:
            sql = "SELECT n FROM generate_series(1, 5) AS n ORDER BY n"
            raw = self.env["sql.console"].export_query_csv(sql)
            parsed = _parse_csv(raw)
            self.assertEqual(len(parsed) - 1, 5)
        finally:
            if saved is not None:
                self._set_param("bemade_sql_console.export_row_cap", saved)

    def test_export_enforces_admin_check(self):
        """A non-member calling export_query_csv raises AccessError."""
        non_admin = new_test_user(
            self.env,
            login="sql_console_export_nobody",
            groups="base.group_user",
        )
        with mute_logger(
            "odoo.addons.bemade_sql_console.models.sql_console"
        ):
            with self.assertRaises(AccessError):
                (
                    self.env["sql.console"]
                    .with_user(non_admin)
                    .export_query_csv("SELECT 1")
                )
