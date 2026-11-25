from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _timesheet_service_generation(self):
        """Copy the product template's « to bring » lines to the visit of each
        task created now. Done after super(), once bemade_fsm has hung the
        line's task under its visit task (when the line sits in a visit
        section), so the lines land on the visit, not on the work subtask."""
        without_task = self.filtered(lambda line: not line.task_id)
        res = super()._timesheet_service_generation()
        for line in without_task:
            template = line.product_id.bemade_task_template_id
            if line.task_id and template:
                template.sudo()._fsm_prep_copy_to(line.task_id.sudo())
        return res
