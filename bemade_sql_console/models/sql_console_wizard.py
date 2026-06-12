"""sql.console.wizard — transient UI model for the SQL console form view."""

import base64
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.fields import Datetime

_logger = logging.getLogger(__name__)


class SqlConsoleWizard(models.TransientModel):
    """Transient wizard holding the SQL editor and its results.

    The wizard calls ``sql.console.run_query`` — so the security path
    (group check, RO connection, guard) is identical for UI and RPC callers.
    """

    _name = "sql.console.wizard"
    _description = "Read-only SQL Console Wizard"

    sql_text = fields.Text(
        string="SQL Query",
        help="Enter a single SELECT or WITH statement.",
    )
    # Full result envelope ({columns, rows, row_count, truncated}) read by the
    # sql_result_table OWL widget. fields.Json keeps it as a structured object
    # client-side rather than a raw JSON string.
    result_json = fields.Json(
        string="Result",
        readonly=True,
    )
    row_count = fields.Integer(
        string="Row Count",
        readonly=True,
    )
    truncated = fields.Boolean(
        string="Truncated",
        readonly=True,
        help="True when more rows exist beyond the configured row cap.",
    )
    error_message = fields.Text(
        string="Error",
        readonly=True,
    )
    csv_file = fields.Binary(
        string="CSV Export",
        readonly=True,
        attachment=False,
    )
    csv_filename = fields.Char(
        string="CSV Filename",
        readonly=True,
    )

    def action_run_query(self):
        """Execute the SQL and stash the result envelope into display fields."""
        self.ensure_one()
        self.write(
            {
                "result_json": False,
                "row_count": 0,
                "truncated": False,
                "error_message": False,
            }
        )
        try:
            result = self.env["sql.console"].run_query(self.sql_text or "")
            self.write(
                {
                    "result_json": result,
                    "row_count": result["row_count"],
                    "truncated": result["truncated"],
                }
            )
        except (UserError, Exception) as exc:
            self.write({"error_message": str(exc)})

        return self._reload_action()

    def action_export_csv(self):
        """Export the FULL result (export cap, not UI cap) as a CSV download.

        Re-runs the same guarded RO path via ``sql.console.export_query_csv``
        (which enforces the admin group check) and delivers the bytes as a
        browser download through ``/web/content``.
        """
        self.ensure_one()
        self.write({"error_message": False})
        try:
            csv_bytes = self.env["sql.console"].export_query_csv(self.sql_text or "")
        except (UserError, Exception) as exc:
            self.write({"error_message": str(exc)})
            return self._reload_action()

        filename = "sql_console_export_%s.csv" % Datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        self.write(
            {
                "csv_file": base64.b64encode(csv_bytes),
                "csv_filename": filename,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/%s/%s/csv_file/%s?download=true"
                % (self._name, self.id, filename)
            ),
            "target": "self",
        }

    def _reload_action(self):
        """Re-open this wizard's form view (target=new) after a write."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
