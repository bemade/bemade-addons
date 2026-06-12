"""sql.console.wizard — transient UI model for the SQL console form view."""

import json
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

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
    result_columns = fields.Text(
        string="Columns",
        readonly=True,
    )
    result_rows = fields.Text(
        string="Rows (JSON)",
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

    def action_run_query(self):
        """Execute the SQL and stash the result envelope into display fields."""
        self.ensure_one()
        self.write(
            {
                "result_columns": False,
                "result_rows": False,
                "row_count": 0,
                "truncated": False,
                "error_message": False,
            }
        )
        try:
            result = self.env["sql.console"].run_query(self.sql_text or "")
            self.write(
                {
                    "result_columns": json.dumps(result["columns"], ensure_ascii=False),
                    "result_rows": json.dumps(result["rows"], ensure_ascii=False),
                    "row_count": result["row_count"],
                    "truncated": result["truncated"],
                }
            )
        except (UserError, Exception) as exc:
            self.write({"error_message": str(exc)})

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
