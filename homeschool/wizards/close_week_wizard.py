# -*- coding: utf-8 -*-
"""« Fermer la semaine » (UC-21): every weekly indicator of the week on one screen, then the
Sunday questions and the week's summary.

Same pattern as « Fermer la journée » (UC-19): a multi-step transient whose **Next**
writes at once and re-opens the wizard on the same record (``_reopen``) — the indicator
lines are persisted before the form opens, so the web client only sends the typed values
back, and abandoning loses nothing already written. Values are text so that a blank stays
a blank (no row); a typed ``0`` is a value.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.day import iso_week_label

R3_CODE = "R3-PARENTS"
R3_PARTS = ("R3-PARENTS-D", "R3-PARENTS-M")
R3_COMPUTED_NOTE = "moyenne D/M (calculé)"
R3_ALERT_BELOW = 3.0


def _format_number(value):
    """``2.5`` → ``"2.5"``, ``3.0`` → ``"3"`` (no float noise, no exponent)."""
    return ("%.4f" % value).rstrip("0").rstrip(".")


class CloseWeekWizard(models.TransientModel):
    _name = "homeschool.close.week.wizard"
    _description = "Close the week"

    step = fields.Selection([("start", "Week"), ("indicators", "Indicators"), ("review", "Review")],
                            default="start", required=True)
    student_id = fields.Many2one("homeschool.student", string="Student", ondelete="cascade")
    multi_student = fields.Boolean(compute="_compute_multi_student")
    date = fields.Date(string="A day of the week", default=lambda self: self._default_week_date(),
                       help="Any date in the week under review.")
    iso_week = fields.Char(compute="_compute_week", string="Week")
    week_start = fields.Date(compute="_compute_week", string="Monday")
    week_end = fields.Date(compute="_compute_week", string="Sunday")
    journal_notes = fields.Text(compute="_compute_journal_notes", string="Indicator notes from the journal",
                                help="The week's journal indicator notes, one line per day: what the counts are tallied from.")
    line_ids = fields.One2many("homeschool.close.week.wizard.line", "wizard_id", string="Indicators")

    # step 2 — the review of the week (found on Next, created on Finish when there is none)
    review_id = fields.Many2one("homeschool.review", string="Review")
    answer_dose = fields.Text(string="Dose kept?", help="Was the planned dose kept this week? Say what changed and why.")
    answer_cap = fields.Text(string="Soft cap — did we stop at the right moments?",
                             help="The cap is no longer a fixed duration: we stop when it makes sense.")
    adjustment = fields.Text(string="Adjustment for next week (within the plan's envelope)")
    notes = fields.Text(help="Markdown.")
    adult_hours = fields.Float(compute="_compute_summary", string="Adult-present hours (week)")
    days_without_journal = fields.Char(compute="_compute_summary", string="Days without a journal entry")
    blank_codes = fields.Char(compute="_compute_summary", string="Indicators still blank this week")
    r3_alert = fields.Boolean(compute="_compute_summary", string="R3-PARENTS below 3 two weeks in a row")

    # ------------------------------------------------------------------
    # defaults and computes
    # ------------------------------------------------------------------
    @api.model
    def _default_week_date(self, today=None):
        """The week to close: this week from Friday on (the Sunday review), otherwise the
        previous one (a catch-up early in the week)."""
        today = today or fields.Date.context_today(self)
        return today if today.weekday() >= 4 else today - timedelta(days=7)

    def _compute_multi_student(self):
        count = self.env["homeschool.student"].search_count([("company_id", "=", self.env.company.id)])
        for wiz in self:
            wiz.multi_student = count > 1

    @api.depends("date")
    def _compute_week(self):
        for wiz in self:
            if wiz.date:
                monday = wiz.date - timedelta(days=wiz.date.weekday())
                wiz.iso_week, wiz.week_start, wiz.week_end = iso_week_label(wiz.date), monday, monday + timedelta(days=6)
            else:
                wiz.iso_week, wiz.week_start, wiz.week_end = False, False, False

    @api.depends("student_id", "date")
    def _compute_journal_notes(self):
        Journal = self.env["homeschool.journal"]
        for wiz in self:
            if not (wiz.student_id and wiz.date):
                wiz.journal_notes = False
                continue
            entries = Journal.search([("student_id", "=", wiz.student_id.id), ("date", ">=", wiz.week_start),
                                      ("date", "<=", wiz.week_end)], order="date, id")
            lines = ["%s : %s" % (fields.Date.to_string(e.date), " ".join(e.indicator_notes.split()))
                     for e in entries if (e.indicator_notes or "").strip()]
            wiz.journal_notes = "\n".join(lines) or False

    @api.depends("student_id", "date", "review_id", "line_ids.value", "step")
    def _compute_summary(self):
        Review = self.env["homeschool.review"]
        for wiz in self:
            if not (wiz.student_id and wiz.date):
                wiz.adult_hours, wiz.days_without_journal, wiz.blank_codes, wiz.r3_alert = 0.0, False, False, False
                continue
            review = wiz.review_id or Review.new({"student_id": wiz.student_id.id, "date": wiz.week_end,
                                                  "company_id": wiz.student_id.company_id.id})
            wiz.adult_hours = review.adult_hours
            wiz.days_without_journal = review.days_without_journal
            wiz.blank_codes = ", ".join(wiz.line_ids.filtered(lambda l: not (l.value or "").strip()).mapped("code"))
            wiz.r3_alert = wiz._r3_alert()

    def _week_value(self, indicator, any_date):
        return self.env["homeschool.indicator.value"].search([
            ("indicator_id", "=", indicator.id), ("student_id", "=", self.student_id.id),
            ("iso_week", "=", iso_week_label(any_date))], order="date desc, id desc", limit=1)

    def _r3_alert(self):
        self.ensure_one()
        r3 = self.env["homeschool.indicator"]._by_code(R3_CODE, self.student_id.company_id)
        if not r3:
            return False
        this_week, previous = self._week_value(r3, self.week_end), self._week_value(r3, self.week_end - timedelta(days=7))
        return bool(this_week and previous and this_week.value < R3_ALERT_BELOW and previous.value < R3_ALERT_BELOW)

    # ------------------------------------------------------------------
    # the lines
    # ------------------------------------------------------------------
    def _indicators_for_week(self):
        """``[(indicator, is_monthly)]`` in csv order: the weekly non-computed indicators of
        the student's family except R3-PARENTS, plus the monthly ones when the week ends the
        month, the month has no value yet, or this week already holds one."""
        self.ensure_one()
        Indicator, Value = self.env["homeschool.indicator"], self.env["homeschool.indicator.value"]
        company, sunday = self.student_id.company_id, self.week_end
        base = [("computed", "=", False), ("company_id", "=", company.id)]
        weekly = Indicator.search(base + [("period", "=", "weekly"), ("code", "!=", R3_CODE)])
        monthly = Indicator.search(base + [("period", "=", "monthly")])
        month_end = (sunday + timedelta(days=7)).month != sunday.month
        if monthly and not month_end:
            first = sunday.replace(day=1)
            last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            with_value = Value.search([("indicator_id", "in", monthly.ids), ("student_id", "=", self.student_id.id),
                                       ("date", ">=", first), ("date", "<=", last)]).mapped("indicator_id")
            this_week = Value.search([("indicator_id", "in", monthly.ids), ("student_id", "=", self.student_id.id),
                                      ("iso_week", "=", self.iso_week)]).mapped("indicator_id")
            monthly = monthly - (with_value - this_week)
        both = (weekly | monthly).sorted(lambda i: (i.csv_sequence, i.code))
        return [(ind, ind in monthly) for ind in both]

    def _load_lines(self):
        """(Re)build the lines from what is recorded for the student and the week."""
        self.ensure_one()
        Value = self.env["homeschool.indicator.value"]
        commands = [fields.Command.clear()]
        for indicator, is_monthly in self._indicators_for_week():
            existing = self._week_value(indicator, self.week_end)
            last = Value.search([("indicator_id", "=", indicator.id), ("student_id", "=", self.student_id.id),
                                 ("date", "<", self.week_start)], order="date desc, id desc", limit=1)
            commands.append(fields.Command.create({
                "indicator_id": indicator.id,
                "is_monthly": is_monthly,
                "value_id": existing.id,
                "value": _format_number(existing.value) if existing else False,
                "note": existing.note or False,
                "last_value_label": "%s (%s)" % (_format_number(last.value), fields.Date.to_string(last.date)) if last else False,
            }))
        self.write({"line_ids": commands, "step": "indicators"})

    @api.model
    def _parse(self, text, code):
        """``""`` → ``None`` (blank: no row); ``2,5`` / ``2.5`` → ``2.5``; else a UserError."""
        text = (text or "").strip().replace(" ", "")
        if not text:
            return None
        try:
            return float(text.replace(",", "."))
        except ValueError:
            raise UserError(self.env._("%(code)s: « %(value)s » is not a number.", code=code, value=text))

    def _write_lines(self):
        """Every line: blank → no row (a pre-loaded row is deleted); a value → the week's row
        created (dated the Sunday) or updated in place. All lines are parsed first."""
        self.ensure_one()
        Value = self.env["homeschool.indicator.value"]
        parsed = [(line, self._parse(line.value, line.code)) for line in self.line_ids]
        for line, number in parsed:
            existing = line.value_id.exists() or self._week_value(line.indicator_id, self.week_end)
            note = (line.note or "").strip() or False
            if number is None:
                if existing:
                    existing.unlink()
                continue
            if existing:
                vals = {}
                if existing.value != number:
                    vals["value"] = number
                if (existing.note or False) != note:
                    vals["note"] = note
                if vals:
                    existing.write(vals)
            else:
                Value.create({"indicator_id": line.indicator_id.id, "student_id": self.student_id.id,
                              "date": self.week_end, "value": number, "note": note,
                              "company_id": self.student_id.company_id.id})

    def _write_r3_parents(self):
        """R3-PARENTS = mean of D and M when both have a value this week; otherwise the row
        this wizard computed earlier goes (a row entered otherwise is left alone)."""
        self.ensure_one()
        Indicator, Value = self.env["homeschool.indicator"], self.env["homeschool.indicator.value"]
        company = self.student_id.company_id
        r3 = Indicator._by_code(R3_CODE, company)
        parts = [Indicator._by_code(code, company) for code in R3_PARTS]
        if not r3 or not all(parts):
            return
        values = [self._week_value(part, self.week_end) for part in parts]
        existing = Value.search([("indicator_id", "=", r3.id), ("student_id", "=", self.student_id.id),
                                 ("iso_week", "=", self.iso_week)])
        if all(values):
            mean = round(sum(v.value for v in values) / len(values), 2)
            vals = {"value": mean, "note": R3_COMPUTED_NOTE}
            if existing:
                existing[:1].write(vals)
            else:
                Value.create(dict(vals, indicator_id=r3.id, student_id=self.student_id.id, date=self.week_end,
                                  company_id=company.id))
        else:
            existing.filtered(lambda v: v.note == R3_COMPUTED_NOTE).unlink()

    def _write_adult_hours(self):
        """R1-ADULTE for the week, when at least one block of the week holds adult minutes
        (never a zero nobody entered)."""
        self.ensure_one()
        recorded = self.env["homeschool.block"].search_count([
            ("student_id", "=", self.student_id.id), ("day_id.iso_week", "=", self.iso_week), ("adult_recorded", "=", True)])
        if recorded:
            self.env["homeschool.indicator"].record_adult_hours(self.student_id, self.week_end,
                                                                note="recorded on closing the week")

    # ------------------------------------------------------------------
    # navigation
    # ------------------------------------------------------------------
    def _reopen(self):
        self.ensure_one()
        name = self.env._("Close the week — %s", self.iso_week) if self.step != "start" else self.env._("Close the week")
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context, dialog_size="extra-large"),
        }

    @api.model
    def action_open(self, student=None, any_date=None):
        """Track › Close the week (no argument) or the review's button: straight to the
        indicators when the student is known — given, or the family's only one; several
        students → the first screen asks which one (never assume a single student)."""
        if not student:
            students = self.env["homeschool.student"].search([("company_id", "=", self.env.company.id)], limit=2)
            student = students if len(students) == 1 else students.browse()
        wiz = self.create({"student_id": student.id, "date": any_date or self._default_week_date()})
        if student:
            wiz._load_lines()
        return wiz._reopen()

    def action_load(self):
        """First screen → the week's indicators."""
        self.ensure_one()
        if not (self.student_id and self.date):
            raise UserError(self.env._("Choose the student and a day of the week."))
        self._load_lines()
        return self._reopen()

    def action_change_week(self):
        """Back to the first screen (what Next already wrote stays written)."""
        self.ensure_one()
        self.line_ids.unlink()
        self.step = "start"
        return self._reopen()

    def action_next(self):
        """Write the lines, R3-PARENTS and R1-ADULTE, then the review screen (the week's
        existing review pre-loaded, whatever its kind)."""
        self.ensure_one()
        self._write_lines()
        self._write_r3_parents()
        self._write_adult_hours()
        review = self.env["homeschool.review"].search([("student_id", "=", self.student_id.id),
                                                       ("iso_week", "=", self.iso_week)], order="id", limit=1)
        self._load_lines()  # the lines as written (ids of the new rows)
        self.write({
            "step": "review", "review_id": review.id,
            "answer_dose": review.answer_dose or False, "answer_cap": review.answer_cap or False,
            "adjustment": review.adjustment or False, "notes": review.notes or False,
        })
        return self._reopen()

    def action_previous(self):
        """Back to the indicators, as recorded; nothing is written."""
        self.ensure_one()
        self._load_lines()
        return self._reopen()

    def action_finish(self):
        """Save the answers on the week's review (created weekly, dated the Sunday, when
        there is none) and open it."""
        self.ensure_one()
        vals = {"answer_dose": self.answer_dose or False, "answer_cap": self.answer_cap or False,
                "adjustment": self.adjustment or False, "notes": self.notes or False}
        review = self.review_id
        if review:
            changed = {k: v for k, v in vals.items() if (review[k] or False) != v}
            if changed:
                review.write(changed)
        else:
            review = self.env["homeschool.review"].create(dict(vals, student_id=self.student_id.id, date=self.week_end,
                                                               kind="weekly"))
        return {
            "type": "ir.actions.act_window",
            "res_model": "homeschool.review",
            "res_id": review.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }


class CloseWeekWizardLine(models.TransientModel):
    _name = "homeschool.close.week.wizard.line"
    _description = "Close the week: one indicator"
    _order = "id"

    wizard_id = fields.Many2one("homeschool.close.week.wizard", required=True, ondelete="cascade")
    indicator_id = fields.Many2one("homeschool.indicator", string="Indicator", required=True, ondelete="cascade")
    code = fields.Char(related="indicator_id.code")
    name = fields.Char(related="indicator_id.name")
    unit = fields.Char(related="indicator_id.unit")
    threshold = fields.Char(related="indicator_id.threshold")
    is_monthly = fields.Boolean()
    marker = fields.Char(compute="_compute_marker", string="Cadence")
    last_value_label = fields.Char(string="Last value")
    value_id = fields.Many2one("homeschool.indicator.value", string="Recorded value", ondelete="set null")
    value = fields.Char(help="Leave blank when not measured: a blank writes nothing, a zero is a value. 2,5 and 2.5 are both accepted.")
    note = fields.Char()

    @api.depends("is_monthly")
    def _compute_marker(self):
        for line in self:
            line.marker = self.env._("monthly") if line.is_monthly else False
