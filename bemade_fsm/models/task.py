from odoo import fields, models, api, Command
from odoo.addons.project.models.project_task import CLOSED_STATES
import re


class Task(models.Model):
    _inherit = "project.task"

    work_order_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="task_work_order_contact_rel",
        column1="task_id",
        column2="res_partner_id",
    )

    site_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="task_site_contact_rel",
        column1="task_id",
        column2="res_partner_id",
    )

    # Override related field to make it return false if this is an FSM subtask
    allow_billable = fields.Boolean(
        string="Can be billed",
        related=False,
        compute="_compute_allow_billable",
        store=True,
    )

    visit_id = fields.Many2one(
        comodel_name="bemade_fsm.visit",
        string="Visit",
    )

    relevant_order_lines = fields.Many2many(
        comodel_name="sale.order.line",
        store=False,
        compute="_compute_relevant_order_lines",
    )

    work_order_number = fields.Char(readonly=True)

    propagate_assignment = fields.Boolean(
        help="Propagate assignment of this task to all subtasks.",
        default=False,
    )

    is_closed = fields.Boolean(
        compute="_compute_is_closed",
    )

    root_ancestor = fields.Many2one(
        comodel_name="project.task",
        compute="_compute_root_ancestor",
        recursive=True,
    )

    def _compute_is_closed(self):
        for rec in self:
            rec.is_closed = rec.state in CLOSED_STATES

    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        for rec in res:
            if rec.parent_id and rec.is_fsm:
                rec.partner_id = rec.parent_id.partner_id
                if not rec.work_order_contacts and rec.parent_id:
                    rec.work_order_contacts = rec.parent_id.work_order_contacts
                if not rec.site_contacts and rec.parent_id:
                    rec.site_contacts = rec.parent_id.site_contacts
            if rec.sale_order_id:
                seq = 1
                prev_seqs = (
                    self.sale_order_id.tasks_ids
                    and self.sale_order_id.tasks_ids.mapped("work_order_number")
                )
                if prev_seqs:
                    pattern = re.compile(r"(\d+)$")
                    matches = map(lambda n: pattern.search(n), prev_seqs)
                    seq += max(map(lambda n: int(n.group(1)) if n else 0, matches))
                rec.work_order_number = (
                    rec.sale_order_id.name.replace("SO", "SVR", 1) + f"-{seq}"
                )
                # If the task is linked to a sales order and has no parent, it should inherit SO work order contacts
                if (
                    not rec.parent_id
                    and not rec.work_order_contacts
                    and rec.sale_order_id.work_order_contacts
                ):
                    rec.work_order_contacts = rec.sale_order_id.work_order_contacts
                if (
                    not rec.parent_id
                    and not rec.site_contacts
                    and rec.sale_order_id.site_contacts
                ):
                    rec.site_contacts = rec.sale_order_id.site_contacts
        return res

    def write(self, vals):
        # Check if we're adding new child tasks
        adding_children = False
        if 'child_ids' in vals:
            for command in vals['child_ids']:
                # Command format is [command_code, id, values]
                # Command code 0 is CREATE, 1 is UPDATE, 4 is LINK
                if command[0] in [0, 1, 4]:
                    adding_children = True
                    break
        
        res = super().write(vals)
        if not self:  # End recursion on empty RecordSet
            return res
        if "propagate_assignment" in vals:
            # When a user sets propagate assignment, it should propagate that setting all the way down the chain
            self.child_ids.write({"propagate_assignment": vals["propagate_assignment"]})
        if "user_ids" in vals:
            to_propagate = self.filtered(lambda task: task.propagate_assignment)
            # Here we use child_ids instead of _get_all_subtasks() so as to allow for setting propagate_assignment
            # to false on a child task.
            to_propagate.child_ids.write({"user_ids": vals["user_ids"]})
        for rec in self:
            if rec.child_ids:
                child_vals = {}
                # If we're adding new children or these fields are being updated, propagate them
                if "site_contacts" in vals or adding_children:
                    child_vals.update(
                        site_contacts=[Command.set(rec.site_contacts.ids)]
                    )
                if "work_order_contacts" in vals or adding_children:
                    child_vals.update(
                        work_order_contacts=[Command.set(rec.work_order_contacts.ids)]
                    )
                if "partner_id" in vals or adding_children:
                    child_vals.update(partner_id=rec.partner_id.id)
                if child_vals:
                    rec.child_ids.write(child_vals)
        return res

    @api.depends("sale_order_id")
    def _compute_relevant_order_lines(self):
        for rec in self:
            rec.relevant_order_lines = (
                rec.sale_order_id
                and rec.sale_order_id.get_relevant_order_lines(rec)
                or False
            )

    def _get_closed_stage_by_project(self):
        """Gets the stage representing completed tasks for each project in
        self.project_id. Copied from industry_fsm/.../project.py:217-221
        for consistency.

        :returns: Dict of project.project -> project.task.type"""
        return {
            project: (
                project.type_ids.filtered(lambda stage: stage.is_closed)[:1]
                or project.type_ids[-1:]
            )
            for project in self.project_id
        }

    @api.depends("parent_id.visit_id", "project_id.is_fsm", "project_id.allow_billable")
    def _compute_allow_billable(self):
        for rec in self:
            # If an FSM task has a parent that is linked to an SO line, then the parent is the billable one
            if (
                rec.parent_id
                and not rec.parent_id.visit_id
                and rec.project_id
                and rec.project_id.is_fsm
            ):
                rec.allow_billable = False
            else:
                rec.allow_billable = rec.project_id.allow_billable

    def _fsm_create_sale_order_line(self):
        # Override to not generate new lines for tasks that are just linked to a visit item
        self.ensure_one()
        if self.visit_id:
            return
        else:
            super()._fsm_create_sale_order_line()

    def action_fsm_validate(self, stop_running_timers=False):
        # Override to close out subtasks as well
        all_tasks = self | self._get_all_subtasks()
        return super(Task, all_tasks).action_fsm_validate(stop_running_timers)

    def _get_full_hierarchy(self):
        if self.child_ids:
            return self | self.child_ids._get_full_hierarchy()
        return self

    def synchronize_name_fsm(self):
        """Applies naming to the entire task tree for tasks that are part of this
        recordset. Root tasks are named:

            Partner Shipping Name - Sale Line Name (Template Name)

        Child tasks with sale_line_id are named by their template if set, sale line name
        if not.

        Child tasks not linked to sale lines are left with their original names."""

        all_tasks = self | self._get_all_subtasks()
        for rec in all_tasks:
            assert rec.is_fsm, "This method should only be called on FSM tasks."

            template = rec.sale_line_id and rec.sale_line_id.product_id.task_template_id

            if template:
                title = template.name
            elif rec.sale_line_id:
                name_parts = rec.sale_line_id.name.split("\n")
                title = name_parts and name_parts[0] or rec.sale_line_id.product_id.name
            elif rec.visit_id:
                title = rec.visit_id.label
            else:
                rec.name = rec.name
                return

            client_name = rec.sale_order_id.partner_shipping_id.name

            if not rec.parent_id:
                rec.name = f"{rec.work_order_number} - {client_name} - {title}"
            else:
                rec.name = title

    @api.depends("parent_id", "parent_id.root_ancestor")
    def _compute_root_ancestor(self):
        for rec in self:
            rec.root_ancestor = rec.parent_id and rec.parent_id.root_ancestor or self

    @api.depends(
        "partner_id",
        "sale_line_id.order_partner_id",
        "parent_id.sale_line_id",
        "project_id.sale_line_id",
        "milestone_id.sale_line_id",
        "allow_billable",
    )
    def _compute_sale_line(self):
        """Override to prevent subtasks from inheriting parent's sale_line_id.

        In the base implementation, if a task and its parent share the same commercial partner,
        the task will inherit the parent's sale_line_id. This causes issues with our FSM tasks
        where we explicitly want subtasks to NOT have a sale_line_id set.
        """

        # Only run on root tasks
        subtasks = self.filtered("parent_id")
        (subtasks - subtasks.filtered("sale_line_id")).sale_line_id = False
        super(Task, self - subtasks)._compute_sale_line()
