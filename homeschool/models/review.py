# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models

from .day import iso_week_label
from .markdown_mixin import markdown_html_field


class Review(models.Model):
    _name = "homeschool.review"
    _description = "Weekly or periodic review"
    _inherit = ["mail.thread", "homeschool.markdown.mixin"]
    _order = "date desc"
    _markdown_fields = ("notes",)

    kind = fields.Selection(
        [("weekly", "Weekly (Sunday)"), ("six_weeks", "Six weeks"), ("january", "January"), ("june", "June")],
        required=True, default="weekly",
    )
    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade")
    date = fields.Date(required=True, default=fields.Date.context_today)
    iso_week = fields.Char(compute="_compute_iso_week", store=True)
    name = fields.Char(compute="_compute_name", store=True)

    answer_dose = fields.Text(string="Dose kept?", help="No adjustment before the 6-week review.")
    answer_cap = fields.Text(string="Visible cap respected?")
    answer_recorded = fields.Text(string="Week recorded as it was?")
    adjustment = fields.Text(string="Adjustment for next week (within the plan's envelope)")
    notes = fields.Text(help="Markdown.")
    notes_html = markdown_html_field("notes")

    missing_indicator_ids = fields.Many2many("homeschool.indicator", compute="_compute_gaps", string="Indicators without a value this week")
    days_without_journal = fields.Char(compute="_compute_gaps")
    adult_hours = fields.Float(compute="_compute_gaps", string="Adult-present hours (week)")

    @api.depends("date")
    def _compute_iso_week(self):
        for rec in self:
            rec.iso_week = iso_week_label(rec.date) if rec.date else False

    @api.depends("kind", "iso_week", "date")
    def _compute_name(self):
        labels = dict(self._fields["kind"].selection)
        for rec in self:
            rec.name = "%s — %s" % (labels.get(rec.kind, rec.kind), rec.iso_week or rec.date)

    @api.depends("date", "student_id")
    def _compute_gaps(self):
        Day = self.env["homeschool.day"]
        for rec in self:
            if not rec.date or not rec.student_id:
                rec.missing_indicator_ids = False
                rec.days_without_journal = ""
                rec.adult_hours = 0.0
                continue
            rec.missing_indicator_ids = self.env["homeschool.indicator"].missing_for_week(rec.date)
            rec.adult_hours = self.env["homeschool.indicator"].adult_hours_for_week(rec.student_id, rec.date)
            monday = rec.date - timedelta(days=rec.date.weekday())
            gaps = []
            for offset in range(5):
                d = monday + timedelta(days=offset)
                if d > fields.Date.context_today(self):
                    break
                day = Day.search([("student_id", "=", rec.student_id.id), ("date", "=", d)], limit=1)
                if not day or (not day.is_off and not day.journal_ids):
                    gaps.append(fields.Date.to_string(d))
            rec.days_without_journal = ", ".join(gaps)
