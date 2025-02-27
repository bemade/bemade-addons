from odoo import models


class ProjectTask(models.Model):
    _inherit = "project.task"

    def write(self, vals):
        # Store old stage for comparison
        old_stages = {task.id: task.stage_id for task in self}

        # Execute original write method
        result = super().write(vals)

        # If stage changed and new stage has an approval template, send the email
        if "stage_id" in vals:
            for task in self.filtered(
                lambda task: task.stage_id != old_stages[task.id]
                and task.stage_id.approval_template_id
            ):
                task._portal_ensure_token()
                task.stage_id.approval_template_id.send_mail(
                    task.id,
                    force_send=True,
                    email_values={
                        "email_to": task.partner_id.email if task.partner_id else False
                    },
                )

        return result
