from odoo import _, api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _timesheet_create_task(self, project):
        """Override to use template if available, otherwise fall back to standard creation."""
        if not self.product_id.task_template_id:
            return super()._timesheet_create_task(project)

        template = self.product_id.task_template_id
        task = template.create_task_from_self(
            project=project,
            name=f"{self.order_id.name}: {template.name}",
        )
        # If template has a partner, keep it, otherwise use SO partner
        if not task.partner_id:
            task.partner_id = self.order_id.partner_id.id
        self.write({"task_id": task.id})
        # Post message on task
        task_msg = _(
            "This task has been created from: %s (%s)",
            self.order_id._get_html_link(),
            self.product_id.name,
        )
        task.message_post(body=task_msg)
        return task

    def _timesheet_create_task_prepare_values(self, project):
        """Override to use template values if available."""
        values = super()._timesheet_create_task_prepare_values(project)
        if self.product_id.task_template_id:
            template = self.product_id.task_template_id
            values.update(
                {
                    "description": template.description
                    or values.get("description", ""),
                    "allocated_hours": template.allocated_hours
                    or values.get("allocated_hours", 0.0),
                    "user_ids": (
                        [(6, 0, template.assignee_ids.ids)]
                        if template.assignee_ids
                        else values.get("user_ids", False)
                    ),
                    "partner_id": template.partner_id.id if template.partner_id else values.get("partner_id", False),
                }
            )
        return values
