# -*- coding: utf-8 -*-
"""Journal API (UC-15): the household's journal tool writes the day's records over RPC.

Every method is ``@api.model`` and public, hence callable as
``POST /json/2/homeschool.journal.api/<method>`` (JSON body = the keyword arguments,
``Authorization: Bearer <API key>`` of a **Homeschool / Manager** user) or through
XML-RPC ``execute_kw``. Each one takes the ``student_id`` and works for any student of any
family the caller manages; nothing here assumes one student or one company.

The mapping between a journal line and the records lives in ``homeschool.importer``'s
per-row methods — the API builds the same row a CSV would hold and applies it through
them, so what the household tool logs and what the nightly export writes back stay one
thing (UC-11's round trip is the proof).
"""
import base64
import binascii

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

def _cell(value):
    """A CSV cell for ``value``: a list joins with ``;``, ``None`` is blank, else text."""
    if value is None or value is False:
        return ""
    if isinstance(value, (list, tuple)):
        return ";".join(str(v).strip() for v in value if str(v).strip())
    return str(value)


class JournalAPI(models.AbstractModel):
    _name = "homeschool.journal.api"
    _description = "Journal API (RPC entry points of the household's journal tool)"

    # ------------------------------------------------------------------
    # guards
    # ------------------------------------------------------------------
    @api.model
    def _student(self, student_id):
        """The student behind ``student_id`` for a manager who can read him; the returned
        recordset runs in the student's company (his family), like ``import_all`` does."""
        if not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a homeschool manager may write the journal."))
        student = self.env["homeschool.student"].browse(int(student_id))
        if not student.exists():
            raise UserError(self.env._("No student with id %s.", student_id))
        student.check_access("read")
        return student.with_company(student.company_id)

    @api.model
    def _importer(self, student):
        return self.env["homeschool.importer"].with_company(student.company_id)

    @api.model
    def _date(self, value):
        d = fields.Date.to_date(value)
        if not d:
            raise UserError(self.env._("A date is required (YYYY-MM-DD)."))
        return d

    # ------------------------------------------------------------------
    # hours
    # ------------------------------------------------------------------
    @api.model
    def log_hours(self, student_id, date, block, activity, matieres, minutes_total, minutes_adult_present,
                  notes="", aliases=None):
        """One ``hours.csv`` row: ``block`` is the key (``bloc-fle``, ``lecture``, ``bonus-st``,
        ``journee``…), ``matieres`` a string (``FLE;MATH``) or a list, minutes are integers or
        ``None`` for "not recorded" (a blank is honest, a zero is a value). ``aliases`` maps
        household keys to ``[kind, subject_code]``. Returns ``{"day_id", "block_id", "log"}``;
        ``block_id`` is ``None`` for a day-off marker (``journee`` with no minutes)."""
        student = self._student(student_id)
        d = self._date(date)
        row = {
            "date": fields.Date.to_string(d),
            "block": _cell(block),
            "activity": _cell(activity),
            "matieres": _cell(matieres),
            "minutes_total": "" if minutes_total is None or minutes_total is False else str(int(minutes_total)),
            "minutes_adult_present": "" if minutes_adult_present is None or minutes_adult_present is False else str(int(minutes_adult_present)),
            "notes": _cell(notes),
        }
        log = []
        day, block_rec = self._importer(student)._apply_hours_row(student, row, aliases, log)
        return {"day_id": day.id, "block_id": block_rec.id or None, "log": log}

    # ------------------------------------------------------------------
    # notes
    # ------------------------------------------------------------------
    @api.model
    def log_note(self, student_id, date, text):
        """Append to the day's journal entry. ``text`` is one bullet (``Ce qui a marché : …``
        → what worked, ``Ce qui a mal été : …`` → what went badly, anything else → notes) or
        several ``- `` bullets at once (a whole day logged late). Today's entry grows in
        place; a past day's entry is never rewritten — the text goes to ``corrections`` as a
        dated line. A day without an entry yet gets one holding the text (nothing to
        correct). Returns ``{"journal_id", "day_id", "corrected"}``."""
        student = self._student(student_id)
        d = self._date(date)
        text = (text or "").strip()
        if not text:
            raise UserError(self.env._("Nothing to write: the note is empty."))
        importer = self._importer(student)
        bullets = importer._parse_bullets(text) or [text]
        vals = importer._journal_vals(bullets)
        day = self.env["homeschool.day"]._get_or_create(student, d)
        Journal = self.env["homeschool.journal"]
        entry = Journal.search([("day_id", "=", day.id)], limit=1)
        corrected = False
        if entry:
            corrected = entry._is_past()
            for field_name, value in vals.items():
                if value:
                    entry.append_note(field_name, value)
        else:
            entry = Journal.create(dict(vals, day_id=day.id))
        return {"journal_id": entry.id, "day_id": day.id, "corrected": corrected}

    # ------------------------------------------------------------------
    # traces
    # ------------------------------------------------------------------
    @api.model
    def log_trace(self, student_id, date, trace_id, title, matieres, pda_ids, diffusion, notes="",
                  attachment=None, artifact_path=None):
        """One ``traces.csv`` row: ``trace_id`` the ``TR-<date>-<letter>`` code (empty → the
        next free one of that day in the family), ``matieres`` / ``pda_ids`` strings or lists,
        ``diffusion`` ``INTERNAL`` / ``INSTITUTIONAL``. ``attachment`` = ``{"name", "data_b64"}``
        is stored once as an ``ir.attachment`` on the trace; ``artifact_path`` is the file's
        path in the family repository (the CSV column), when the caller keeps one. The trace
        is the parent's: ``submitted_by="parent"``, ``validated=True``. Returns
        ``{"trace_id", "code", "log"}`` — ``trace_id`` is the record id."""
        student = self._student(student_id)
        d = self._date(date)
        code = (trace_id or "").strip()
        if not code:
            code = self.env["homeschool.trace"]._next_code(d, student.company_id)
        row = {
            "trace_id": code,
            "date": fields.Date.to_string(d),
            "title": _cell(title),
            "matieres": _cell(matieres),
            "pda_ids": _cell(pda_ids),
            "artifact_path": _cell(artifact_path),
            "diffusion": _cell(diffusion),
            "notes": _cell(notes),
        }
        log = []
        importer = self._importer(student)
        trace = importer._apply_trace_row(student, row, log, extra_vals={"submitted_by": "parent", "validated": True})
        if attachment:
            name = (attachment.get("name") or "").strip()
            data = attachment.get("data_b64") or ""
            if not name or not data:
                raise UserError(self.env._("An attachment needs a name and its base64 content (data_b64)."))
            try:
                raw = base64.b64decode(data, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise UserError(self.env._("The attachment is not valid base64: %s", exc)) from exc
            importer._attach_trace_file(trace, name, raw)
        return {"trace_id": trace.id, "code": trace.code, "log": log}

    # ------------------------------------------------------------------
    # indicators
    # ------------------------------------------------------------------
    @api.model
    def log_indicator(self, student_id, date, code, value, notes=""):
        """One ``indicateurs.csv`` row: the value of indicator ``code`` (of the student's
        family) on ``date``, created or updated in place. ``value`` is a number or its text
        (``2,5`` accepted). An unknown code or a missing value is an error: a skipped
        indicator has no row, never a zero that was not said. Returns
        ``{"value_id", "created"}``."""
        student = self._student(student_id)
        d = self._date(date)
        raw = "" if value is None or value is False else str(value).strip()
        if raw == "":
            raise UserError(self.env._("A value is required: a skipped indicator has no row, never a zero that was not said."))
        row = {"date": fields.Date.to_string(d), "id": _cell(code).strip(), "valeur": raw, "notes": _cell(notes)}
        log = []
        try:
            value_rec, created = self._importer(student)._apply_indicator_row(student, row, log)
        except ValueError as exc:
            raise UserError(self.env._("Not a number: %s", raw)) from exc
        if not value_rec:
            raise UserError(self.env._("Unknown indicator %(code)s for this family.", code=row["id"]))
        return {"value_id": value_rec.id, "created": created}

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    @api.model
    @api.readonly
    def status(self, student_id, date):
        """Where the day stands, with the rule of the household's ``journal.py status``:
        ``hours_rows`` (the rows ``hours.csv`` would hold for the day, the ``journee`` marker
        included), ``adult_missing`` (blocks with minutes but no adult-present minutes),
        ``journal_entry`` (an entry exists) and ``done`` = rows exist, nothing missing, an
        entry exists. ``day_id`` is ``None`` when the day does not exist yet."""
        student = self._student(student_id)
        d = self._date(date)
        day = self.env["homeschool.day"].search([("student_id", "=", student.id), ("date", "=", d)], limit=1)
        if not day:
            return {"day_id": None, "hours_rows": 0, "adult_missing": 0, "journal_entry": False, "done": False}
        hours_rows = len(self.env["homeschool.exporter"]._hours_rows(day))
        adult_missing = len(day.block_ids.filtered("adult_missing"))
        journal_entry = bool(day.journal_ids)
        return {
            "day_id": day.id,
            "hours_rows": hours_rows,
            "adult_missing": adult_missing,
            "journal_entry": journal_entry,
            "done": bool(hours_rows and not adult_missing and journal_entry),
        }
