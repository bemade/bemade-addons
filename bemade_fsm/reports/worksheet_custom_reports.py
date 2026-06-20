from odoo import models


class TaskCustomReport(models.AbstractModel):
    _inherit = "report.industry_fsm.worksheet_custom"

    def _get_report_values(self, docids, data=None):
        vals = super()._get_report_values(docids, data)
        # Sort tasks by sequence to allow user-defined order in PDF reports
        if vals.get("docs"):
            vals["docs"] = vals["docs"].sorted(key=lambda t: (t.sequence, t.id))
        split_time_materials = (
            self.env.company.split_time_from_materials_on_service_work_orders
        )
        vals.update({"split_time_materials": split_time_materials})
        return vals
