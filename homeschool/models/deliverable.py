# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError


class Deliverable(models.Model):
    """One line of the day's « liste du jour »: what the student is expected to hand over,
    at what moment, ticked when done. Bound to a day, like blocks and journal entries, so
    the student and the family are the day's."""
    _name = "homeschool.deliverable"
    _description = "Deliverable (liste du jour)"
    _order = "day_id, sequence, id"

    day_id = fields.Many2one("homeschool.day", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one(related="day_id.student_id", store=True)
    company_id = fields.Many2one(related="day_id.company_id", store=True, index=True)
    date = fields.Date(related="day_id.date", store=True)
    sequence = fields.Integer(default=10)
    plan_key = fields.Char(index=True, help="Stable key of this deliverable in the day's plan (replays of log_plan match on it).")
    name = fields.Char(required=True)
    detail = fields.Text(help="What exactly, how much, where it goes.")
    when = fields.Char(help="A moment of the day as written on the paper list: '9 h', 'after lunch', 'bonus'.")
    bonus = fields.Boolean(help="Optional extra: not counted against the day.")
    done = fields.Boolean()
    done_at = fields.Datetime(readonly=True)
    done_by = fields.Many2one("res.users", readonly=True)

    # the only field a portal user may write; see write()
    PORTAL_WRITABLE = frozenset({"done"})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("done"):
                vals.setdefault("done_at", fields.Datetime.now())
                vals.setdefault("done_by", self.env.user.id)
        return super().create(vals_list)

    def write(self, vals):
        """A portal user (the student — the record rule limits him to his own student's
        deliverables) may only tick or untick; anything else is refused. Ticking stamps
        ``done_at`` / ``done_by`` with the user who ticked, unticking clears them."""
        if self.env.user.share and not self.env.su:
            forbidden = set(vals) - self.PORTAL_WRITABLE
            if forbidden:
                raise AccessError(self.env._(
                    "From the portal, a deliverable can only be ticked or unticked (not %(fields)s).",
                    fields=", ".join(sorted(forbidden)),
                ))
        if "done" in vals:
            vals = dict(vals)
            if vals["done"]:
                vals.setdefault("done_at", fields.Datetime.now())
                vals.setdefault("done_by", self.env.user.id)
            else:
                vals["done_at"] = False
                vals["done_by"] = False
        return super().write(vals)
