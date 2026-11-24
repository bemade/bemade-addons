from odoo import api, fields, models
from odoo.tools.misc import format_datetime


class FsmPrepLine(models.Model):
    """One item to bring to a field service visit (a tool or free text).

    Not billed: it never touches the sale order, the delivery or the invoice.
    """

    _name = "fsm.prep.line"
    _description = "To Bring Line"
    _order = "sequence, id"

    task_id = fields.Many2one(
        "project.task",
        string="Visit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    tool_id = fields.Many2one("fsm.service.tool", string="Tool", ondelete="restrict")
    name = fields.Char(
        string="Description",
        compute="_compute_name",
        store=True,
        readonly=False,
        required=True,
        precompute=True,
    )
    quantity = fields.Integer(default=1, required=True)
    checked = fields.Boolean(string="Checked", copy=False)
    checked_by_id = fields.Many2one(
        "res.users", string="Checked By", readonly=True, copy=False
    )
    checked_at = fields.Datetime(string="Checked On", readonly=True, copy=False)
    checked_label = fields.Char(string="Check", compute="_compute_checked_label")
    overbooked = fields.Boolean(
        compute="_compute_overbooking",
        help="Visits planned on overlapping dates (the end extended by the "
        "tool's return delay) need more of this tool than the quantity owned. "
        "Visits without a start and an end date are ignored.",
    )
    overbooking_note = fields.Char(
        string="Overbooking", compute="_compute_overbooking"
    )

    _quantity_positive = models.Constraint(
        "CHECK (quantity > 0)",
        "The quantity to bring must be positive.",
    )

    @api.depends("tool_id")
    def _compute_name(self):
        for line in self:
            if line.tool_id:
                line.name = line.tool_id.name

    @api.depends("checked_by_id", "checked_at")
    def _compute_checked_label(self):
        # Follows the stamp only: the visit's onchange writes a preview stamp
        # when a toggle flips (see project.task), which refreshes this label.
        for line in self:
            if line.checked_by_id and line.checked_at:
                line.checked_label = self.env._(
                    "Checked by %(user)s on %(date)s",
                    user=line.checked_by_id.name,
                    date=format_datetime(self.env, line.checked_at, dt_format="short"),
                )
            else:
                line.checked_label = False

    # -- check stamp (server side) ------------------------------------------------

    def _check_stamp_vals(self, vals):
        """Drop client values for the stamp and set it from ``checked``."""
        vals = dict(vals)
        vals.pop("checked_by_id", None)
        vals.pop("checked_at", None)
        if "checked" in vals:
            if vals["checked"]:
                vals.update(
                    checked_by_id=self.env.uid, checked_at=fields.Datetime.now()
                )
            else:
                vals.update(checked_by_id=False, checked_at=False)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._check_stamp_vals(vals) for vals in vals_list])

    def write(self, vals):
        if "checked" in vals:
            # Re-ticking an already ticked line keeps the first stamp.
            changed = self.filtered(lambda l: l.checked != bool(vals["checked"]))
            unchanged = self - changed
            stamp = self._check_stamp_vals(vals)
            plain = self._check_stamp_vals(
                {k: v for k, v in vals.items() if k != "checked"}
            )
            res = True
            if changed:
                res = super(FsmPrepLine, changed).write(stamp)
            if unchanged and plain:
                res = super(FsmPrepLine, unchanged).write(plain)
            return res
        vals = self._check_stamp_vals(vals)
        return super().write(vals) if vals else True

    # -- overbooking --------------------------------------------------------------

    @api.depends(
        "tool_id",
        "tool_id.quantity_owned",
        "tool_id.return_delay_days",
        "quantity",
        "task_id",
        "task_id.planned_date_begin",
        "task_id.date_deadline",
        "task_id.state",
    )
    def _compute_overbooking(self):
        self.overbooked = False
        self.overbooking_note = False
        tool_lines = self.filtered("tool_id")
        for task, lines in tool_lines.grouped("task_id").items():
            usage = task._fsm_prep_tool_usage(lines.tool_id)
            for line in lines:
                data = usage.get(line.tool_id.id)
                if data and data["over"]:
                    line.overbooked = True
                    line.overbooking_note = data["note"]
