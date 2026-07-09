from odoo import models, fields, api, Command


class TaskTemplate(models.Model):
    _name = "project.task.template"
    _description = "Template for new project tasks"
    _order = "sequence, id"

    @api.model
    def _current_company(self):
        return self.env.company

    name = fields.Char(string="Task Title", required=True)

    description = fields.Html()

    assignees = fields.Many2many(
        comodel_name="res.users",
        string="Default Assignees",
        help="Employees assigned to tasks created from this template.",
    )

    customer = fields.Many2one(
        comodel_name="res.partner",
        string="Default Customer",
        help="Default customer for tasks created from this template.",
        default=lambda self: self.parent.customer if self.parent else False,
    )

    project = fields.Many2one(
        comodel_name="project.project",
        string="Default Project",
        help="Default project for tasks created from this template.",
    )

    tags = fields.Many2many(
        comodel_name="project.tags",
        string="Default Tags",
        help="Default tags for tasks created from this template.",
    )

    parent = fields.Many2one(
        comodel_name="project.task.template",
        string="Parent Task Template",
        ondelete="cascade",
    )

    subtasks = fields.One2many(
        comodel_name="project.task.template",
        inverse_name="parent",
        string="Subtask Templates",
    )
    sequence = fields.Integer()

    company_id = fields.Many2one(
        comodel_name="res.company", string="Company", index=1, default=_current_company
    )

    planned_hours = fields.Float("Initially Planned Hours")

    equipment_ids = fields.Many2many(
        comodel_name="fsm.equipment",
        relation="bemade_fsm_task_template_equipment_rel",
        column1="task_template_id",
        column2="equipment_id",
        string="Equipment to Service",
    )

    def action_open_task(self):
        return {
            "view_mode": "form",
            "res_model": "project.task.template",
            "res_id": self.id,
            "type": "ir.actions.act_window",
            "context": self._context,
        }

    @api.onchange("customer")
    def _onchange_customer(self):
        for rec in self:
            new_equipment_ids = [
                eq.id for eq in rec.equipment_ids if eq.partner_id == rec.customer
            ]
            rec.write({"equipment_ids": [Command.set(new_equipment_ids)]})

    def _prepare_new_task_values_from_self(self, project, name=False, parent_id=False):
        partner_id = self.customer or self.parent.customer or False
        if not partner_id and parent_id:
            parent = self.env["project.task"].browse(parent_id)
            partner_id = parent.partner_id or parent.sale_order_id.partner_shipping_id
        vals = {
            "project_id": project.id,
            "name": name or self.name,
            "description": self.description,
            "parent_id": parent_id,
            "user_ids": self.assignees.ids,
            "tag_ids": self.tags.ids,
            "allocated_hours": self.planned_hours,
            "sequence": self.sequence,
            "equipment_ids": (
                [Command.set(self.equipment_ids.ids)] if self.equipment_ids else False
            ),
            "partner_id": partner_id and partner_id.id,
            "company_id": self.company_id.id,
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
        for seq, rec in enumerate(self):
            vals = rec._prepare_new_task_values_from_self(project, name, parent_id)
            # Assign an explicit ascending sequence per sibling so the created
            # child_ids preserve template order. project.task._order ends in
            # "id desc", so siblings that all share the template's (usually 0)
            # sequence would otherwise come back in reverse creation order.
            vals["sequence"] = seq
            task = rec.env["project.task"].create(vals)
            rec.subtasks.create_task_from_self(project, name=False, parent_id=task.id)
            tasks |= task
        return tasks
