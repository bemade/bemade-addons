# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import AccessError


class ReadingBook(models.Model):
    """A book of the student's « carnet de lecture »: one record per book, the daily
    entries hang from it. Belongs to the student's family."""
    _name = "homeschool.reading.book"
    _description = "Reading log: book"
    _inherit = ["mail.thread", "homeschool.company.mixin"]
    _order = "finished desc nulls first, started desc, id desc"
    _rec_name = "title"

    student_id = fields.Many2one("homeschool.student", required=True, ondelete="cascade", index=True, check_company=True)
    title = fields.Char(required=True)
    author = fields.Char()
    started = fields.Date(help="When the student started the book.")
    finished = fields.Date(help="When the student finished it; empty while reading.")
    entry_ids = fields.One2many("homeschool.reading.entry", "book_id", string="Entries")
    entry_count = fields.Integer(compute="_compute_entry_count")
    note = fields.Text()

    @api.depends("entry_ids")
    def _compute_entry_count(self):
        for rec in self:
            rec.entry_count = len(rec.entry_ids)


class ReadingEntry(models.Model):
    """One reading-log entry per book per day: two words, a question and its answer; on
    Fridays the weekly page. Written by the student himself from the portal (or by the
    parent on his behalf)."""
    _name = "homeschool.reading.entry"
    _description = "Reading log: entry"
    _order = "date desc, id desc"

    book_id = fields.Many2one("homeschool.reading.book", required=True, ondelete="cascade", index=True)
    student_id = fields.Many2one(related="book_id.student_id", store=True)
    company_id = fields.Many2one(related="book_id.company_id", store=True, index=True)
    date = fields.Date(required=True, default=fields.Date.context_today, index=True)
    word1 = fields.Char(string="Word 1", help="A word met today.")
    word2 = fields.Char(string="Word 2")
    question = fields.Text(help="A question about today's reading.")
    answer = fields.Text(help="The student's answer.")
    weekly_page = fields.Text(help="The Friday page: what the week's reading was about.")
    written_by = fields.Many2one("res.users", default=lambda self: self.env.user, readonly=True)

    _book_date_unique = models.Constraint(
        "unique(book_id, date)", "There is already an entry for this book on that day."
    )

    @api.depends("book_id.title", "date")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %s" % (rec.book_id.title or "", rec.date or "")

    # an entry stays on its book and keeps its author: a portal user cannot move it
    # (the write rule is checked before the write, so the guard is here) nor sign otherwise
    PORTAL_LOCKED = frozenset({"book_id", "written_by", "student_id", "company_id"})

    @api.model_create_multi
    def create(self, vals_list):
        # a portal user writes as himself, whatever he sends
        if self.env.user.share and not self.env.su:
            for vals in vals_list:
                vals["written_by"] = self.env.user.id
        return super().create(vals_list)

    def write(self, vals):
        if self.env.user.share and not self.env.su:
            locked = set(vals) & self.PORTAL_LOCKED
            if locked:
                raise AccessError(self.env._(
                    "From the portal, a reading entry cannot be moved or re-signed (%(fields)s).",
                    fields=", ".join(sorted(locked)),
                ))
        return super().write(vals)
