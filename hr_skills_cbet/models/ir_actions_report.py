from odoo import api, models
from odoo.tools.safe_eval import safe_eval, time


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _cbet_print_name(self, report, record):
        """The file name (without extension) a report gives *record* — the same
        expression the download controller evaluates (``print_report_name``)."""
        if not report.print_report_name:
            return record.display_name
        return safe_eval(report.print_report_name, {"object": record, "time": time})
