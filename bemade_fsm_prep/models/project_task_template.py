from odoo import fields, models


class ProjectTaskTemplate(models.Model):
    _inherit = "project.task.template"

    fsm_prep_template_line_ids = fields.One2many(
        "fsm.prep.template.line",
        "template_id",
        string="To Bring",
        copy=True,
        help="Tools and materials to bring, copied to the visit (the top-level "
        "task) when this template is applied.",
    )

    def _fsm_prep_all_template_lines(self):
        """The « to bring » lines of these templates and all their sub-templates,
        in template order."""
        lines = self.env["fsm.prep.template.line"]
        for template in self:
            lines |= template.fsm_prep_template_line_ids
            lines |= template.subtasks._fsm_prep_all_template_lines()
        return lines

    def _fsm_prep_copy_to(self, task):
        """Append the « to bring » lines of this template tree to ``task``'s visit."""
        self.ensure_one()
        template_lines = self._fsm_prep_all_template_lines()
        if not template_lines or not task:
            return
        visit = task._fsm_prep_visit()
        self.env["fsm.prep.line"].create(
            [
                dict(line._prepare_prep_line_vals(), task_id=visit.id)
                for line in template_lines
            ]
        )

    def create_task_from_self(self, project, name=False, parent_id=False):
        if self.env.context.get("fsm_prep_no_copy"):
            return super().create_task_from_self(project, name, parent_id)
        tasks = super(
            ProjectTaskTemplate, self.with_context(fsm_prep_no_copy=True)
        ).create_task_from_self(project, name, parent_id)
        tasks = tasks.with_env(self.env)
        for template, task in zip(self, tasks):
            template.sudo()._fsm_prep_copy_to(task)
        return tasks
