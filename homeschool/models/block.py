# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .markdown_mixin import markdown_html_field

BLOCK_KINDS = [
    ("opening", "Opening"),
    ("bloc", "Bloc"),
    ("pause", "Pause"),
    ("reading", "Reading"),
    ("projects", "Projects"),
    ("ressource", "Ressource"),
    ("debrief", "Debrief"),
    ("bonus", "Bonus"),
]

BLOCK_STATUS = [
    ("planned", "Planned"),
    ("done", "Done"),
    ("partial", "Partial"),
    ("skipped", "Skipped"),
]


def float_to_time(value):
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    if minutes == 60:
        hours, minutes = hours + 1, 0
    return time(min(hours, 23), minutes)


class Block(models.Model):
    _name = "homeschool.block"
    _description = "Planning block"
    _inherit = ["mail.thread", "homeschool.markdown.mixin"]
    _order = "day_id, sequence, id"
    _markdown_fields = ("intention", "steps", "success", "fallback", "note")

    day_id = fields.Many2one("homeschool.day", required=True, ondelete="cascade", index=True, tracking=True)
    student_id = fields.Many2one(related="day_id.student_id", store=True)
    date = fields.Date(related="day_id.date", store=True)
    sequence = fields.Integer(default=10, tracking=True)
    kind = fields.Selection(BLOCK_KINDS, required=True, default="bloc")
    subject_id = fields.Many2one("homeschool.subject", ondelete="restrict")
    name = fields.Char(required=True)
    duration_planned = fields.Integer(string="Planned (min)", default=45)
    anchored = fields.Boolean(help="Start at a fixed time instead of after the previous block.")
    start_fixed = fields.Float(help="Fixed start time (hours), when anchored.")
    start_time = fields.Float(compute="_compute_times", store=True, readonly=True)
    end_time = fields.Float(compute="_compute_times", store=True, readonly=True)
    start_datetime = fields.Datetime(compute="_compute_times", store=True, readonly=True)
    stop_datetime = fields.Datetime(compute="_compute_times", store=True, readonly=True)
    duration_hours = fields.Float(compute="_compute_times", store=True, readonly=True, help="Planned duration in hours (calendar view).")

    intention = fields.Text(help="Markdown.")
    intention_html = markdown_html_field("intention")
    steps = fields.Text(help="Markdown.")
    steps_html = markdown_html_field("steps")
    success = fields.Text(string="Success criteria", help="Markdown.")
    success_html = markdown_html_field("success")
    fallback = fields.Text(help="Markdown.")
    fallback_html = markdown_html_field("fallback")
    note = fields.Text(help="Markdown.")
    note_html = markdown_html_field("note")

    item_ids = fields.Many2many("homeschool.item", "homeschool_block_item_rel", "block_id", "item_id", string="Curriculum items")
    material_ids = fields.Many2many("homeschool.material", "homeschool_block_material_rel", "block_id", "material_id", string="Material")
    project_id = fields.Many2one("homeschool.project", ondelete="set null")
    trace_ids = fields.One2many("homeschool.trace", "block_id", string="Traces")

    status = fields.Selection(BLOCK_STATUS, required=True, default="planned", tracking=True)
    minutes_total = fields.Integer(string="Actual (min)")
    minutes_adult_present = fields.Integer(string="Adult present (min)")
    actuals_recorded = fields.Boolean(help="True once actual minutes were entered for this block.")
    adult_recorded = fields.Boolean(help="True once adult-present minutes were entered (even 0).")
    adult_missing = fields.Boolean(compute="_compute_adult_missing", store=True, help="Actuals entered without adult minutes: honest blank, to fill.")
    color = fields.Integer(related="subject_id.color")

    _duration_positive = models.Constraint(
        "check(duration_planned >= 0)", "A block's planned duration cannot be negative."
    )
    _actuals_positive = models.Constraint(
        "check(minutes_total >= 0 and minutes_adult_present >= 0)", "Minutes cannot be negative."
    )

    # ------------------------------------------------------------------
    # times
    # ------------------------------------------------------------------
    @api.depends("day_id", "day_id.date", "day_id.start_time", "sequence", "duration_planned", "anchored", "start_fixed")
    def _compute_times(self):
        for day in self.mapped("day_id"):
            cursor = day.start_time or 0.0
            for block in day.block_ids.sorted(lambda b: (b.sequence, b.id)):
                start = block.start_fixed if block.anchored else cursor
                end = start + (block.duration_planned or 0) / 60.0
                block.start_time = start
                block.end_time = end
                block.duration_hours = (block.duration_planned or 0) / 60.0
                if day.date:
                    block.start_datetime = datetime.combine(day.date, float_to_time(start))
                    block.stop_datetime = block.start_datetime + timedelta(minutes=block.duration_planned or 0)
                else:
                    block.start_datetime = block.stop_datetime = False
                cursor = end
        for block in self.filtered(lambda b: not b.day_id):
            block.start_time = block.end_time = block.duration_hours = 0.0
            block.start_datetime = block.stop_datetime = False

    @api.constrains("anchored", "start_fixed", "sequence", "duration_planned", "day_id")
    def _check_anchor(self):
        for day in self.mapped("day_id"):
            cursor = day.start_time or 0.0
            for block in day.block_ids.sorted(lambda b: (b.sequence, b.id)):
                if block.anchored:
                    if block.start_fixed + 1e-6 < cursor:
                        raise ValidationError(self.env._(
                            "Block '%(name)s' is anchored at %(fixed).2f but the previous block ends at %(end).2f.",
                            name=block.name, fixed=block.start_fixed, end=cursor,
                        ))
                    cursor = block.start_fixed
                cursor += (block.duration_planned or 0) / 60.0

    # ------------------------------------------------------------------
    # actuals
    # ------------------------------------------------------------------
    @api.depends("actuals_recorded", "adult_recorded", "kind", "status")
    def _compute_adult_missing(self):
        for rec in self:
            rec.adult_missing = bool(rec.actuals_recorded and not rec.adult_recorded and rec.kind != "pause" and rec.status != "skipped")

    @api.constrains("minutes_total", "minutes_adult_present", "adult_recorded")
    def _check_adult_bounded(self):
        for rec in self:
            if rec.adult_recorded and rec.minutes_adult_present > rec.minutes_total:
                raise ValidationError(self.env._("Adult-present minutes cannot exceed the block's total minutes."))

    @api.model
    def _flag_actuals(self, vals):
        if "minutes_total" in vals:
            vals.setdefault("actuals_recorded", vals["minutes_total"] not in (None, False))
        if "minutes_adult_present" in vals:
            vals.setdefault("adult_recorded", vals["minutes_adult_present"] not in (None, False))
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._flag_actuals(vals)
        return super().create(vals_list)

    def write(self, vals):
        return super().write(self._flag_actuals(dict(vals)))

    def action_mark_done(self):
        self.write({"status": "done"})
