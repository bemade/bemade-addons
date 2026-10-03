# -*- coding: utf-8 -*-
from odoo import fields, models

from .markdown_mixin import markdown_html_field


class Journal(models.Model):
    _name = "homeschool.journal"
    _description = "Parent's daily journal"
    _inherit = ["homeschool.markdown.mixin", "homeschool.frozen.mixin"]
    _order = "date desc"
    _markdown_fields = ("went_well", "went_badly", "notes", "corrections")
    # Fields of a past day's entry that are never edited in place: a write appends a dated
    # correction instead (the journal is an append-only record, like the CSVs it replaces).
    _frozen_fields = ("went_well", "went_badly", "notes", "indicator_notes")

    day_id = fields.Many2one("homeschool.day", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one(related="day_id.student_id", store=True)
    company_id = fields.Many2one(related="day_id.company_id", store=True, index=True)
    date = fields.Date(related="day_id.date", store=True)
    went_well = fields.Text(string="What worked", help="Markdown. As it was — a clean journal is a false journal.")
    went_well_html = markdown_html_field("went_well")
    went_badly = fields.Text(string="What went badly", help="Markdown.")
    went_badly_html = markdown_html_field("went_badly")
    notes = fields.Text(help="Markdown.")
    notes_html = markdown_html_field("notes")
    indicator_notes = fields.Text(help="Free text: conflicts, withdrawal, spontaneous engagement, recovery delay — tallied at the weekly review.")
    corrections = fields.Text(help="Dated corrections appended to a past entry. Past entries are never edited in place.")
    corrections_html = markdown_html_field("corrections")

    _day_unique = models.Constraint("unique(day_id)", "There is already a journal entry for that day.")
