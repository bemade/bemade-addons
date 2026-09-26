# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

from .markdown_mixin import markdown_html_field

JOURNAL_STATES = [
    ("future", "Not yet"),
    ("off", "Day off"),
    ("incomplete", "Incomplete"),
    ("done", "Done"),
]


def iso_week_label(d):
    """'2026-W38' for a date (ISO year and week)."""
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


class Day(models.Model):
    _name = "homeschool.day"
    _description = "School day"
    _inherit = ["mail.thread", "homeschool.markdown.mixin"]
    _order = "date desc"
    _markdown_fields = ("opening", "evening_before", "debrief", "note")

    name = fields.Char(compute="_compute_name", store=True)
    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True)
    date = fields.Date(required=True, index=True)
    iso_week = fields.Char(compute="_compute_iso_week", store=True, index=True)
    weekday = fields.Integer(compute="_compute_iso_week", store=True, help="0 = Monday.")
    start_time = fields.Float(default=9.0, help="When the first block starts (hours, e.g. 9.0).")
    is_off = fields.Boolean(string="Day off", tracking=True)
    off_reason = fields.Char()

    opening = fields.Text(help="Markdown: the opening plan (what we do, why, the choice offered).")
    opening_html = markdown_html_field("opening")
    evening_before = fields.Text(help="Markdown: the 'evening before' checklist.")
    evening_before_html = markdown_html_field("evening_before")
    debrief = fields.Text(help="Markdown.")
    debrief_html = markdown_html_field("debrief")
    note = fields.Text(help="Markdown.")
    note_html = markdown_html_field("note")

    block_ids = fields.One2many("homeschool.block", "day_id", string="Blocks")
    block_count = fields.Integer(compute="_compute_totals", store=True)
    planned_minutes = fields.Integer(compute="_compute_totals", store=True)
    actual_minutes = fields.Integer(compute="_compute_totals", store=True)
    adult_minutes = fields.Integer(compute="_compute_totals", store=True)
    end_time = fields.Float(compute="_compute_totals", store=True)
    material_ids = fields.Many2many("homeschool.material", compute="_compute_material_ids", string="Material of the day")

    journal_ids = fields.One2many("homeschool.journal", "day_id")
    journal_state = fields.Selection(JOURNAL_STATES, compute="_compute_journal_state", store=True)

    _student_date_unique = models.Constraint(
        "unique(student_id, date)", "There is already a day for this student on that date."
    )

    @api.depends("date", "student_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.date.strftime("%a %Y-%m-%d") if rec.date else self.env._("New day")

    @api.depends("date")
    def _compute_iso_week(self):
        for rec in self:
            rec.iso_week = iso_week_label(rec.date) if rec.date else False
            rec.weekday = rec.date.weekday() if rec.date else 0

    @api.depends("block_ids.duration_planned", "block_ids.minutes_total", "block_ids.minutes_adult_present",
                 "block_ids.end_time", "block_ids.status")
    def _compute_totals(self):
        for rec in self:
            blocks = rec.block_ids
            rec.block_count = len(blocks)
            rec.planned_minutes = sum(blocks.filtered(lambda b: b.kind != "pause").mapped("duration_planned"))
            rec.actual_minutes = sum(blocks.mapped("minutes_total"))
            rec.adult_minutes = sum(blocks.mapped("minutes_adult_present"))
            rec.end_time = max(blocks.mapped("end_time")) if blocks else rec.start_time

    @api.depends("block_ids.material_ids")
    def _compute_material_ids(self):
        for rec in self:
            rec.material_ids = rec.block_ids.material_ids

    @api.depends("date", "is_off", "block_ids.status", "block_ids.kind", "block_ids.minutes_total",
                 "block_ids.actuals_recorded", "journal_ids")
    def _compute_journal_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.is_off:
                rec.journal_state = "off"
            elif rec.date and rec.date > today:
                rec.journal_state = "future"
            else:
                pending = rec.block_ids.filtered(
                    lambda b: b.kind != "pause" and b.status != "skipped" and not b.actuals_recorded
                )
                rec.journal_state = "incomplete" if (pending or not rec.journal_ids) else "done"

    def action_recompute_times(self):
        self.block_ids._compute_times()
        return True

    @api.model
    def _get_or_create(self, student, date):
        day = self.search([("student_id", "=", student.id), ("date", "=", date)], limit=1)
        return day or self.create({"student_id": student.id, "date": date})

    # ------------------------------------------------------------------
    # Week generation from templates (UC-03)
    # ------------------------------------------------------------------
    @api.model
    def generate_week(self, student, any_date):
        """Create the days and blocks of the ISO week containing ``any_date`` from the
        block templates. Days already holding blocks, and days off, are skipped.
        Returns (days_created, days_skipped)."""
        monday = any_date - timedelta(days=any_date.weekday())
        Template = self.env["homeschool.block.template"]
        created, skipped = self.browse(), self.browse()
        for offset in range(7):
            d = monday + timedelta(days=offset)
            templates = Template._for(student, d.weekday())
            if not templates:
                continue
            day = self._get_or_create(student, d)
            if day.is_off or day.block_ids:
                skipped |= day
                continue
            day.block_ids = [fields.Command.create(t._to_block_vals()) for t in templates]
            created |= day
        return created, skipped
