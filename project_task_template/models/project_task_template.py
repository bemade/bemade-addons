from odoo import models, fields, api, _


class ProjectTaskTemplate(models.Model):
    _name = "project.task.template"
    _description = "Template for new project tasks"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    @api.model
    def _current_company(self):
        return self.env.company

    name = fields.Char(
        string="Task Title",
        required=True,
        tracking=True,
    )

    description = fields.Html(tracking=True)

    assignee_ids = fields.Many2many(
        comodel_name="res.users",
        string="Default Assignees",
        help="Employees assigned to tasks created from this template.",
        tracking=1,
    )

    project_id = fields.Many2one(
        comodel_name="project.project",
        string="Default Project",
        help="Default project for tasks created from this template.",
        tracking=2,
    )

    tag_ids = fields.Many2many(
        comodel_name="project.tags",
        string="Default Tags",
        help="Default tags for tasks created from this template.",
        tracking=3,
    )

    parent_id = fields.Many2one(
        comodel_name="project.task.template",
        string="Parent Task Template",
        ondelete="cascade",
        tracking=4,
    )

    subtask_ids = fields.One2many(
        comodel_name="project.task.template",
        inverse_name="parent_id",
        string="Subtask Templates",
        copy=True,
    )

    sequence = fields.Integer(default=10)

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        index=True,
        default=_current_company,
        tracking=5,
    )

    allocated_hours = fields.Float(
        "Initially Allocated Hours",
        tracking=6,
    )

    active = fields.Boolean(
        default=True,
        tracking=7,
    )

    task_count = fields.Integer(
        string="Tasks",
        compute="_compute_task_count",
    )

    def _compute_task_count(self):
        for template in self:
            template.task_count = self.env["project.task"].search_count(
                [("template_id", "=", template.id)]
            )

    def action_view_tasks(self):
        """Open the tree view of tasks created from this template."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("project.action_view_task")
        action["domain"] = [("template_id", "=", self.id)]
        action["context"] = {
            "default_template_id": self.id,
            "create": False,  # Don't allow creation from this view
        }
        return action

    def action_open_task(self):
        return {
            "view_mode": "form",
            "res_model": "project.task.template",
            "res_id": self.id,
            "type": "ir.actions.act_window",
            "context": self._context,
        }

    def _prepare_new_task_values_from_self(self, project, name=False, parent_id=False):
        """Prepare values for creating a new task from this template.

        :param project: project.project record the task should be added to
        :param name: name for the new task (defaults to template name)
        :param parent_id: parent task for the new task (none by default)
        :return: dict of values for creating the task
        """
        vals = {
            "project_id": project.id,
            "name": name or self.name,
            "description": self.description,
            "parent_id": parent_id,
            "user_ids": self.assignee_ids.ids,
            "tag_ids": self.tag_ids.ids,
            "allocated_hours": self.allocated_hours,
            "sequence": self.sequence,
            "company_id": self.company_id.id,
            "template_id": self.id,
        }
        return vals

    def create_task_from_self(self, project, name=False, parent_id=False):
        """Create a project.task from this template and return it.
        Can be called on a RecordSet of multiple templates.

        :param project: project.project record the task should be added to
        :param name: name for the new task (defaults to template name)
        :param parent_id: parent task for the new task (none by default)
        :return: project.task record created from this template
        """
        tasks = self.env["project.task"]
        for rec in self:
            vals = rec._prepare_new_task_values_from_self(project, name, parent_id)
            task = rec.env["project.task"].create(vals)
            rec.subtask_ids.create_task_from_self(project, name=False, parent_id=task.id)
            tasks |= task
        return tasks

    def copy(self, default=None):
        """Support copying templates, ensuring proper duplication of the task hierarchy."""
        self.ensure_one()
        if default is None:
            default = {}
        if "name" not in default:
            default["name"] = self.name + _(" (copy)")
        # Don't copy parent reference, this will be handled by recursion
        default["parent_id"] = False
        new = super().copy(default)

        # Copy subtasks, linking them to the new template
        for subtask in self.subtask_ids:
            subtask.copy({"parent_id": new.id})

        return new
