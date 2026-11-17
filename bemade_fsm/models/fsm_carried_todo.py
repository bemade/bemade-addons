from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.addons.project.models.project_task import CLOSED_STATES


class FsmCarriedTodo(models.Model):
    """A « to do on the next visit » noted when a visit is closed.

    It is carried to the next visit at the same site (the visit's customer /
    service address) as a subtask « From last visit: ... ». The next visit is
    the earliest open top-level FSM task at the site, by planned start (unplanned
    last), other than the visits it was already carried to. With no such visit,
    the to-do waits (« pending ») until a top-level FSM task is created at the
    site.
    """

    _name = "fsm.carried.todo"
    _description = "To do on the next visit"
    _order = "id desc"

    name = fields.Text(string="To do", required=True)
    partner_id = fields.Many2one(
        "res.partner", string="Site", required=True, index=True, ondelete="cascade"
    )
    equipment_id = fields.Many2one("fsm.equipment", string="Equipment", ondelete="set null")
    source_task_id = fields.Many2one(
        "project.task",
        string="Noted at visit",
        ondelete="set null",
        index="btree_not_null",
    )
    target_task_id = fields.Many2one(
        "project.task",
        string="Subtask",
        ondelete="set null",
        index="btree_not_null",
        readonly=True,
        copy=False,
    )
    target_visit_id = fields.Many2one(
        related="target_task_id.parent_id", string="Next visit"
    )
    visit_ids = fields.Many2many(
        "project.task",
        "fsm_carried_todo_visit_rel",
        "todo_id",
        "task_id",
        string="Carried to visits",
        readonly=True,
        copy=False,
        help="Visits this to-do was carried to. It is not carried to the same "
        "visit twice.",
    )
    state = fields.Selection(
        [
            ("pending", "Waiting for a visit"),
            ("scheduled", "On a visit"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="pending",
        required=True,
        readonly=True,
        copy=False,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    # -- attaching ---------------------------------------------------------------

    @api.model
    def _next_visit_domain(self, partner):
        return [
            ("partner_id", "=", partner.id),
            ("parent_id", "=", False),
            ("is_fsm", "=", True),
            ("is_template", "=", False),
            ("state", "not in", list(CLOSED_STATES)),
        ]

    def _find_next_visit(self):
        self.ensure_one()
        excluded = self.visit_ids | self.source_task_id
        visits = self.env["project.task"].sudo().search(
            self._next_visit_domain(self.partner_id)
            + [("id", "not in", excluded.ids)],
            order="planned_date_begin asc nulls last, id asc",
            limit=1,
        )
        return visits

    def _subtask_name(self):
        self.ensure_one()
        lang = self.partner_id.lang or self.env.lang
        return self.with_context(lang=lang).env._("From last visit: %s", self.name)

    def _subtask_description(self):
        self.ensure_one()
        source = self.source_task_id
        lines = [Markup("<p>%s</p>") % escape(self.name).replace("\n", Markup("<br/>"))]
        if source:
            label = source.work_order_number or source.name
            lines.append(
                Markup('<p>%s <a href="/odoo/project.task/%s">%s</a></p>')
                % (
                    self.with_context(
                        lang=self.partner_id.lang or self.env.lang
                    ).env._("Noted at the close of"),
                    source.id,
                    label,
                )
            )
        return Markup("").join(lines)

    def _attach_to_next_visit(self):
        """Carry each pending to-do of ``self`` to its next visit, if any."""
        Task = self.env["project.task"]
        for todo in self.sudo().filtered(lambda t: t.state == "pending"):
            visit = todo._find_next_visit()
            if not visit:
                continue
            siblings = visit.child_ids
            subtask = Task.with_context(fsm_carried_todo_skip=True).create(
                {
                    "name": todo._subtask_name(),
                    "project_id": visit.project_id.id,
                    "parent_id": visit.id,
                    "partner_id": visit.partner_id.id,
                    "user_ids": [(6, 0, visit.user_ids.ids)],
                    "equipment_ids": [(6, 0, todo.equipment_id.ids)],
                    "description": todo._subtask_description(),
                    "sequence": max(siblings.mapped("sequence") or [0]) + 1,
                    "company_id": visit.company_id.id,
                }
            )
            todo.write(
                {
                    "target_task_id": subtask.id,
                    "visit_ids": [(4, visit.id)],
                    "state": "scheduled",
                }
            )

    @api.model
    def _attach_pending_for_sites(self, partners):
        if not partners:
            return
        self.sudo().search(
            [("partner_id", "in", partners.ids), ("state", "=", "pending")],
            order="id asc",
        )._attach_to_next_visit()

    # -- lifecycle ---------------------------------------------------------------

    def _on_target_state_change(self):
        """The subtask's state changed: done -> done, cancelled -> next visit."""
        to_carry = self.browse()
        for todo in self.sudo():
            state = todo.target_task_id.state
            if todo.state == "cancelled":
                continue
            if state == "1_done":
                todo.state = "done"
            elif state == "1_canceled":
                todo.write({"state": "pending", "target_task_id": False})
                to_carry |= todo
            elif todo.state == "done":
                todo.state = "scheduled"
        to_carry._attach_to_next_visit()

    def _on_target_deleted(self):
        """The subtask (or its visit) was deleted: wait for / go to a visit."""
        todos = self.sudo().filtered(lambda t: t.state in ("scheduled", "done"))
        todos.write({"state": "pending", "target_task_id": False})
        todos._attach_to_next_visit()

    def action_cancel(self):
        for todo in self.sudo():
            subtask = todo.target_task_id
            todo.state = "cancelled"
            if subtask and subtask.state not in CLOSED_STATES:
                subtask.with_context(fsm_carried_todo_skip=True).state = "1_canceled"

    def action_reset(self):
        self.sudo().filtered(lambda t: t.state == "cancelled").write(
            {"state": "pending", "target_task_id": False, "visit_ids": [(5,)]}
        )
        self._attach_to_next_visit()
