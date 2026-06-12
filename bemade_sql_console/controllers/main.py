"""HTTP controller for the streaming CSV export of the read-only SQL console.

The route is the trust boundary for the export: it re-enforces the in-method
``group_sql_console`` check (Odoo's HTTP dispatcher only authenticates, it does
not rights-check the endpoint) and then streams the full query result as CSV
straight from a psycopg2 server-side cursor — no row cap and no buffering of the
whole result set in memory.
"""

import csv
import io
import logging

import werkzeug.exceptions

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.fields import Datetime
from odoo.http import request

_logger = logging.getLogger(__name__)


class SqlConsoleExportController(http.Controller):
    """Streaming CSV download for a wizard's SQL query."""

    @http.route(
        "/bemade_sql_console/export/<int:wizard_id>",
        type="http",
        auth="user",
        methods=["GET"],
        readonly=True,
    )
    def export_csv(self, wizard_id, **kwargs):
        """Stream the wizard's query result as a CSV attachment.

        Security: the ``group_sql_console`` membership check is re-done here —
        this route is the trust boundary, because Odoo authenticates HTTP
        endpoints but does not rights-check them. A non-member gets 403.

        The wizard is browsed in the *user's own env*, so a user can only read
        their own transient wizard record. The query then runs over the exact
        same guarded RO path as ``run_query`` via
        ``sql.console._stream_query_rows`` (single-SELECT guard, SELECT-only
        role connection, app-layer read-only, statement timeout, Decimal→str).
        """
        # Trust boundary — re-enforce the admin group at the route.
        if not request.env.user.has_group(
            "bemade_sql_console.group_sql_console"
        ):
            raise werkzeug.exceptions.Forbidden(
                _("You are not allowed to export SQL console queries.")
            )

        wizard = request.env["sql.console.wizard"].browse(wizard_id)
        # exists() reads the record in the user's env; a missing/foreign
        # transient record yields an empty recordset → 404.
        if not wizard.exists():
            raise werkzeug.exceptions.NotFound()

        sql = wizard.sql_text or ""

        # Resolve the row generator eagerly so configuration / guard / auth
        # errors surface as a clean HTTP error BEFORE we start streaming a
        # 200 response body (you cannot change the status mid-stream).
        console = request.env["sql.console"]
        try:
            rows_gen = console._stream_query_rows(sql)
        except AccessError as exc:
            raise werkzeug.exceptions.Forbidden(str(exc))
        except UserError as exc:
            raise werkzeug.exceptions.BadRequest(str(exc))

        filename = "sql_console_export_%s.csv" % Datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        return request.make_response(
            self._csv_stream(rows_gen),
            headers=[
                ("Content-Type", "text/csv; charset=utf-8"),
                (
                    "Content-Disposition",
                    'attachment; filename="%s"' % filename,
                ),
            ],
        )

    @staticmethod
    def _csv_stream(rows_gen):
        """Yield CSV bytes batch-by-batch from the row generator.

        Reuses a single StringIO buffer that is truncated after each flush, so
        only one batch of CSV text is ever held in memory at a time. The first
        item from ``rows_gen`` is the header (column names); every subsequent
        item is one data row.
        """
        buf = io.StringIO()
        writer = csv.writer(buf)

        def flush():
            data = buf.getvalue()
            buf.seek(0)
            buf.truncate(0)
            return data.encode("utf-8")

        header = next(rows_gen, None)
        if header is None:
            return  # empty / error-before-header: yield nothing
        writer.writerow(header)
        yield flush()

        # Flush every N rows so the buffer stays small for huge results.
        flush_every = 500
        count = 0
        for row in rows_gen:
            writer.writerow(["" if v is None else v for v in row])
            count += 1
            if count >= flush_every:
                yield flush()
                count = 0
        if count:
            yield flush()
