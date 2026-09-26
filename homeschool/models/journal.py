# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .markdown_mixin import markdown_html_field

# Fields of a past day's entry that are never edited in place: a write appends a dated
# correction instead (the journal is an append-only record, like the CSVs it replaces).
_FROZEN = ("went_well", "went_badly", "notes", "indicator_notes")


class Journal(models.Model):
    _name = "homeschool.journal"
    _description = "Parent's daily journal"
    _inherit = ["homeschool.markdown.mixin"]
    _order = "date desc"
    _markdown_fields = ("went_well", "went_badly", "notes", "corrections")

    day_id = fields.Many2one("homeschool.day", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one(related="day_id.student_id", store=True)
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

    def _is_past(self):
        self.ensure_one()
        return bool(self.date and self.date < fields.Date.context_today(self))

    def write(self, vals):
        """Editing a frozen field of a past entry appends a dated correction instead."""
        frozen = {k: v for k, v in vals.items() if k in _FROZEN}
        if not frozen or self.env.context.get("journal_force_edit"):
            return super().write(vals)
        rest = {k: v for k, v in vals.items() if k not in _FROZEN}
        for rec in self:
            if rec._is_past():
                today = fields.Date.to_string(fields.Date.context_today(self))
                lines = [rec.corrections or ""]
                for field_name, value in frozen.items():
                    label = self._fields[field_name].string
                    lines.append("- **%s** (%s): %s" % (today, label, value or ""))
                super(Journal, rec).write(dict(rest, corrections="\n".join(l for l in lines if l is not None).strip()))
            else:
                super(Journal, rec).write(dict(rest, **frozen))
        return True

    def append_note(self, field_name, text):
        """Append a bullet to a Markdown field (today) or to the corrections (past)."""
        self.ensure_one()
        if self._is_past():
            return self.write({field_name: text})
        current = self[field_name] or ""
        return self.write({field_name: (current + "\n" if current else "") + text})
