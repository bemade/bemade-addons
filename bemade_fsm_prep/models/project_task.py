from collections import defaultdict
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.addons.project.models.project_task import CLOSED_STATES


class ProjectTask(models.Model):
    _inherit = "project.task"

    fsm_prep_line_ids = fields.One2many(
        "fsm.prep.line",
        "task_id",
        string="To Bring",
        copy=True,
        groups="industry_fsm.group_fsm_user",
    )
    fsm_prep_overbooking_warning = fields.Html(
        string="Tool Overbooking",
        compute="_compute_fsm_prep_overbooking_warning",
        sanitize=False,
        groups="industry_fsm.group_fsm_user",
    )

    @api.onchange("fsm_prep_line_ids")
    def _onchange_fsm_prep_lines_preview_stamp(self):
        """Show « Checked by … on … » as soon as a line's toggle flips.

        Flipping a toggle on a list row sends the visit's onchange, and Odoo
        does not report a line compute that follows that same line's change.
        Writing the preview stamp here makes the label recompute and reach the
        client. Display only: the stamp fields are readonly, the client never
        saves them, and fsm.prep.line create/write set the real stamp. A line
        already ticked when loaded keeps its first stamp, as on save.
        """
        for line in self.fsm_prep_line_ids:
            origin = line._origin
            if line.checked and origin.checked:
                if line.checked_by_id != origin.checked_by_id:
                    line.checked_by_id = origin.checked_by_id
                    line.checked_at = origin.checked_at
            elif line.checked:
                if not line.checked_by_id:
                    line.checked_by_id = self.env.user
                    line.checked_at = fields.Datetime.now()
            elif line.checked_by_id:
                line.checked_by_id = False
                line.checked_at = False

    def _fsm_prep_visit(self):
        """The visit of this task: its top-level ancestor (itself when it has
        no parent). Template « to bring » lines are copied there."""
        self.ensure_one()
        task = self
        while task.parent_id:
            task = task.parent_id
        return task

    def _apply_template_to_self(self, template=None):
        """Also append the template tree's « to bring » lines to the visit.

        super() instantiates the sub-templates through create_task_from_self,
        which would copy their lines itself; the context flag stops it so the
        tree is copied once, here."""
        if template is None:
            template = self.template_id
        res = super()._apply_template_to_self(
            template.with_context(fsm_prep_no_copy=True) if template else template
        )
        if template:
            template.sudo()._fsm_prep_copy_to(self)
        return res

    def _fsm_prep_tool_usage(self, tools):
        """For each of ``tools`` used on this visit, the need of this visit and
        of the other open visits planned on overlapping dates.

        Overlap uses the Planning window, ``planned_date_begin`` to
        ``date_deadline``, extended past the end by the tool's return delay:
        two visits needing a tool conflict when one starts before the other's
        end plus that tool's delay. A visit without both dates is ignored, as
        are done or cancelled visits and this visit's own hierarchy (its
        sub-tasks carry the same dates).

        :return: {tool id: {"need", "others", "owned", "over", "visits", "note"}}
        """
        self.ensure_one()
        result = {}
        task = self.sudo()
        if (
            not tools
            or not task.planned_date_begin
            or not task.date_deadline
            or task.state in CLOSED_STATES
        ):
            return result
        lines = task.fsm_prep_line_ids.filtered(lambda l: l.tool_id in tools)
        need = defaultdict(int)
        for line in lines:
            need[line.tool_id.id] += line.quantity
        if not need:
            return result
        # In a form (onchange), self is a new record: use the saved one.
        origin = task._origin
        own_ids = []
        if origin:
            root = origin._fsm_prep_visit()
            own_ids = origin.search([("id", "child_of", root.id)]).ids
        tools = self.env["fsm.service.tool"].sudo().browse(list(need))
        delays = {tool.id: timedelta(days=tool.return_delay_days) for tool in tools}
        # One search over the window widened by the longest delay, then the
        # exact window of each tool.
        widest = max(delays.values())
        others = (
            self.env["fsm.prep.line"]
            .sudo()
            .search(
                [
                    ("tool_id", "in", list(need)),
                    ("task_id", "not in", own_ids),
                    ("task_id.is_fsm", "=", True),
                    ("task_id.state", "not in", list(CLOSED_STATES)),
                    ("task_id.planned_date_begin", "<", task.date_deadline + widest),
                    ("task_id.date_deadline", ">", task.planned_date_begin - widest),
                ]
            )
        )
        other_qty = defaultdict(int)
        other_visits = defaultdict(lambda: self.env["project.task"])
        for line in others:
            delay = delays[line.tool_id.id]
            other = line.task_id
            if (
                other.planned_date_begin < task.date_deadline + delay
                and other.date_deadline + delay > task.planned_date_begin
            ):
                other_qty[line.tool_id.id] += line.quantity
                other_visits[line.tool_id.id] |= other
        for tool in tools:
            total = need[tool.id] + other_qty[tool.id]
            visits = other_visits[tool.id]
            over = total > tool.quantity_owned
            note = False
            if over:
                note = self.env._(
                    "%(total)s needed, %(owned)s owned",
                    total=total,
                    owned=tool.quantity_owned,
                )
                if visits:
                    note += " — " + ", ".join(visits.mapped("display_name"))
            result[tool.id] = {
                "tool": tool,
                "need": need[tool.id],
                "others": other_qty[tool.id],
                "owned": tool.quantity_owned,
                "over": over,
                "visits": visits,
                "note": note,
            }
        return result

    @api.depends(
        "fsm_prep_line_ids.tool_id",
        "fsm_prep_line_ids.quantity",
        "fsm_prep_line_ids.tool_id.return_delay_days",
        "planned_date_begin",
        "date_deadline",
        "state",
    )
    def _compute_fsm_prep_overbooking_warning(self):
        for task in self:
            usage = task._fsm_prep_tool_usage(task.sudo().fsm_prep_line_ids.tool_id)
            over = [data for data in usage.values() if data["over"]]
            if not over:
                task.fsm_prep_overbooking_warning = False
                continue
            items = Markup("").join(
                Markup("<li><b>%s</b> : %s / %s needed, %s owned%s</li>")
                % (
                    data["tool"].name,
                    Markup("%s requis, %s possédé(s)")
                    % (data["need"] + data["others"], data["owned"]),
                    data["need"] + data["others"],
                    data["owned"],
                    (
                        Markup(" — visites / visits : %s")
                        % ", ".join(data["visits"].mapped("display_name"))
                        if data["visits"]
                        else ""
                    ),
                )
                for data in over
            )
            task.fsm_prep_overbooking_warning = (
                Markup(
                    "<div><b>Outil réservé en trop / Tool overbooked</b>"
                    "<ul class='mb-0'>%s</ul></div>"
                )
                % items
            )
