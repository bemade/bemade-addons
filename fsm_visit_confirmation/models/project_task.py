from odoo import models, fields


class ProjectTask(models.Model):
    _inherit = "project.task"

    # Visit notification fields - designed for extensibility
    # Each checkbox informs the customer about conditions during the service visit
    water_shutdown_required = fields.Boolean(
        string="Water Shutdown Required",
        default=False,
        help="Check if the customer will not have water during this service visit.",
    )

    water_shutdown_notes = fields.Text(
        string="Water Shutdown Notes",
        help="Additional notes about the water shutdown (e.g., duration, timing).",
    )

    def write(self, vals):
        # Store old stage for comparison
        old_stages = {task.id: task.stage_id for task in self}

        # Execute original write method
        result = super().write(vals)

        # If stage changed and new stage has an approval template, send the email
        if "stage_id" in vals:
            # Only send email for top-level tasks
            for task in self.filtered(
                lambda task: task.stage_id != old_stages[task.id]
                and task.stage_id.approval_template_id
                and not task.parent_id
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
