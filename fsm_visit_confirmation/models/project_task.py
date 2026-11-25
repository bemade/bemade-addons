from markupsafe import Markup

from odoo import models, fields


class ProjectTask(models.Model):
    _inherit = "project.task"

    # Many2many relation to client requirements - extensible without code changes
    client_requirement_ids = fields.Many2many(
        "fsm.task.client.requirement",
        "project_task_client_requirement_rel",
        "task_id",
        "requirement_id",
        string="Client Requirements",
        help="Select client-facing requirements for this visit. "
        "These will be communicated in the confirmation email.",
    )

    # Notes field for additional context about requirements
    client_requirements_notes = fields.Text(
        string="Requirements Notes",
        help="Additional notes about requirements (e.g., duration, timing, specific instructions).",
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

    def _action_customer_approve(self):
        """Record the customer's approval of the visit (Approve link of the
        confirmation email).

        Marks the task approved and posts one bilingual note (French first,
        then English). If the task is still in a stage that carries an approval
        template and that stage names an ``approved_stage_id``, the task moves
        there. A task moved by hand in the meantime stays where it is.
        """
        for task in self:
            stage = task.stage_id
            target = (
                stage.approved_stage_id if stage.approval_template_id else False
            )
            task.write({"state": "03_approved"})
            if target:
                task.write({"stage_id": target.id})
                installed = dict(self.env["res.lang"].get_installed())
                fr_name = (
                    target.with_context(lang="fr_FR").name
                    if "fr_FR" in installed
                    else target.name
                )
                en_name = target.with_context(lang="en_US").name
                body = Markup(
                    "Visite approuvée par le client ; tâche déplacée à "
                    "l'étape « %s ».<br/>Visit approved by customer; task "
                    "moved to stage \u201c%s\u201d."
                ) % (fr_name, en_name)
            else:
                body = Markup(
                    "Visite approuvée par le client.<br/>"
                    "Visit approved by customer."
                )
            task.message_post(
                body=body,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
        return True
