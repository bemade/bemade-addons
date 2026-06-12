"""
US-09 — Streaming CSV export (uncapped, server-side cursor).

Acceptance criteria
-------------------
- sql.console._stream_query_rows(sql) is a generator whose first item is the
  list of column names and whose remaining items are the result rows. Assembled
  through the controller's CSV writer it yields a CSV whose header == columns and
  whose data rows match the query result.
- Values containing a comma, newline or double-quote are properly quoted (csv
  module quoting), surviving a round-trip through csv.reader.
- The export is UNCAPPED: a result larger than the UI row_cap (and the old
  100k export cap) streams completely — generate_series(1, 5000) yields all
  5000 data rows.
- Security: the streaming path enforces the same admin group check (AccessError
  for a non-member of group_sql_console), and the HTTP route returns 403
  Forbidden for a non-member.

Notes
-----
The local Odoo runner serves tests under a PreforkServer that exposes no HTTP
port (HttpCase.http_port() → AttributeError), so browser/url_open HTTP tests
cannot run here. The export path is therefore verified at the model/controller
layer: the factored generator (``_stream_query_rows``) drives the controller's
CSV assembler (``_csv_stream``) to assert content, quoting and the absence of a
cap; security is asserted by the AccessError the generator raises on first
advance (the controller advances eagerly and maps it to HTTP 403 Forbidden).
"""

import csv
import io

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sql_console.controllers.main import (
    SqlConsoleExportController,
)

from .common import SqlConsoleTestBase


def _assemble_csv(rows_gen):
    """Drive _csv_stream over the row generator and parse the result.

    Returns the parsed CSV (list of list of str), exactly as a browser would
    receive and a csv.reader would parse it.
    """
    chunks = b"".join(SqlConsoleExportController._csv_stream(rows_gen))
    text = chunks.decode("utf-8")
    return list(csv.reader(io.StringIO(text)))


@tagged("at_install", "post_install")
class TestCsvStreamModel(SqlConsoleTestBase):
    """US-09 model layer: generator content, quoting, no cap, security."""

    def _set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(key, str(value))

    def test_header_and_rows_match_result(self):
        """CSV header == columns; data rows match the SELECT output."""
        sql = "SELECT n, n * 10 AS ten FROM generate_series(1, 3) AS n ORDER BY n"
        gen = self.env["sql.console"]._stream_query_rows(sql)
        parsed = _assemble_csv(gen)

        self.assertEqual(parsed[0], ["n", "ten"])
        self.assertEqual(parsed[1:], [["1", "10"], ["2", "20"], ["3", "30"]])

    def test_first_yield_is_columns(self):
        """The generator's first item is the column-name list."""
        gen = self.env["sql.console"]._stream_query_rows(
            "SELECT 1 AS a, 2 AS b"
        )
        header = next(gen)
        self.assertEqual(header, ["a", "b"])
        gen.close()

    def test_quoting_comma_newline_quote(self):
        """Values with comma/newline/quote survive a CSV round-trip intact."""
        nasty = 'a,b\nc"d'
        sql = "SELECT $tag$%s$tag$ AS v" % nasty
        gen = self.env["sql.console"]._stream_query_rows(sql)
        parsed = _assemble_csv(gen)

        self.assertEqual(parsed[0], ["v"])
        self.assertEqual(parsed[1], [nasty])

    def test_null_renders_as_empty_field(self):
        """SQL NULL is streamed as an empty CSV field."""
        gen = self.env["sql.console"]._stream_query_rows(
            "SELECT NULL::int AS x, 7 AS y"
        )
        parsed = _assemble_csv(gen)
        self.assertEqual(parsed[1], ["", "7"])

    def test_export_has_no_row_cap(self):
        """A result far larger than the UI/old-export cap streams in FULL.

        Drives 5000 rows through the generator with a tiny UI row_cap set, to
        prove the stream path ignores row_cap entirely.
        """
        self._set_param("bemade_sql_console.row_cap", 1)
        try:
            sql = "SELECT n FROM generate_series(1, 5000) AS n ORDER BY n"
            gen = self.env["sql.console"]._stream_query_rows(sql)
            parsed = _assemble_csv(gen)
            # 1 header + 5000 data rows — nothing dropped.
            self.assertEqual(len(parsed) - 1, 5000)
            self.assertEqual(parsed[1][0], "1")
            self.assertEqual(parsed[-1][0], "5000")
        finally:
            self._set_param("bemade_sql_console.row_cap", 1000)

    def test_decimal_preserved_as_string(self):
        """NUMERIC values keep full precision (Decimal→str), not float."""
        gen = self.env["sql.console"]._stream_query_rows(
            "SELECT 12345.67890::numeric AS amount"
        )
        parsed = _assemble_csv(gen)
        self.assertEqual(parsed[1], ["12345.67890"])

    def test_stream_enforces_admin_check(self):
        """A non-member calling _stream_query_rows raises AccessError eagerly.

        The auth check (and the single-SELECT guard and credential resolution)
        run in _stream_query_rows BEFORE the row generator is returned — so the
        controller can map the error to HTTP 403 before emitting a 200 body.
        """
        non_admin = new_test_user(
            self.env,
            login="sql_console_stream_nobody",
            groups="base.group_user",
        )
        with mute_logger(
            "odoo.addons.bemade_sql_console.models.sql_console"
        ):
            with self.assertRaises(AccessError):
                # No next() needed — _stream_query_rows raises before returning.
                (
                    self.env["sql.console"]
                    .with_user(non_admin)
                    ._stream_query_rows("SELECT 1")
                )


    def test_csv_stream_propagates_error_before_header(self):
        """If the row generator errors before any header, _csv_stream yields none.

        The controller resolves _stream_query_rows eagerly (mapping AccessError
        / UserError to 403 / 400 before the 200 body), but as defense in depth
        _csv_stream must not emit a partial/corrupt body if the generator raises
        before producing a header. Here a guard violation (multi-statement)
        raised eagerly by _stream_query_rows is the realistic case; we assert
        the assembler emits nothing for an immediately-empty generator.
        """
        from odoo.addons.bemade_sql_console.controllers.main import (
            SqlConsoleExportController,
        )

        def empty_gen():
            return
            yield  # pragma: no cover

        chunks = list(SqlConsoleExportController._csv_stream(empty_gen()))
        self.assertEqual(chunks, [], "No header → no CSV body")

    def test_guard_violation_raised_eagerly(self):
        """A multi-statement query is rejected by _stream_query_rows eagerly.

        Proves the controller can surface a guard violation as an HTTP error
        (BadRequest) before streaming, mirroring run_query's UserError.
        """
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.env["sql.console"]._stream_query_rows(
                "SELECT 1; SELECT 2"
            )
