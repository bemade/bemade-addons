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
from odoo.fields import Command

from .block import BLOCK_KINDS

PLAN_DAY_TEXTS = ("opening", "evening_before", "debrief", "note")

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
    # plan (UC-18): the day's plan lives in Odoo
    # ------------------------------------------------------------------
    @api.model
    def _plan_rows(self, plan, kind, date_str):
        """The ``blocks`` or ``deliverables`` rows of a plan, validated before anything is
        written: a list of dicts, each with a non-empty, unique ``key`` and a ``name``; a
        block's ``kind`` must be one of the block kinds. ``None`` when the key is absent
        from the plan (that part of the day is left untouched)."""
        if kind not in plan:
            return None
        rows = plan.get(kind)
        if not isinstance(rows, (list, tuple)) or any(not isinstance(r, dict) for r in rows):
            raise UserError(self.env._("Plan %(date)s: %(part)s must be a list of objects.", date=date_str, part=kind))
        seen = set()
        kinds = {k for k, _label in BLOCK_KINDS}
        for i, row in enumerate(rows):
            key = str(row.get("key") or "").strip()
            if not key:
                raise UserError(self.env._("Plan %(date)s: %(part)s #%(n)d has no key.", date=date_str, part=kind, n=i + 1))
            if key in seen:
                raise UserError(self.env._("Plan %(date)s: duplicate %(part)s key %(key)s.", date=date_str, part=kind, key=key))
            seen.add(key)
            if not str(row.get("name") or "").strip():
                raise UserError(self.env._("Plan %(date)s/%(key)s: a name is required.", date=date_str, key=key))
            if kind == "blocks" and (row.get("kind") or "bloc") not in kinds:
                raise UserError(self.env._("Plan %(date)s/%(key)s: unknown block kind %(kind)s.", date=date_str, key=key, kind=row.get("kind")))
        return rows

    @api.model
    def _plan_block_vals(self, student, row, index, date_str, log):
        """The block values of one plan row; unknown subject, items, material and project go
        to ``log`` and the block is written without them."""
        key = str(row["key"]).strip()
        Subject = self.env["homeschool.subject"]
        Item = self.env["homeschool.item"]
        Material = self.env["homeschool.material"]
        Project = self.env["homeschool.project"]
        company = student.company_id
        subject = Subject.browse()
        subject_code = str(row.get("subject") or "").strip()
        if subject_code:
            subject = Subject._by_csv_key(subject_code, create=False)
            if not subject:
                log.append("plan %s/%s: unknown subject %r" % (date_str, key, subject_code))
        items = Item.browse()
        for code in row.get("items") or []:
            code = str(code).strip()
            item = Item._by_code(code) if code else Item.browse()
            if item:
                items |= item
            else:
                log.append("plan %s/%s: unknown item %r" % (date_str, key, code))
        materials = Material.browse()
        for path in row.get("materials") or []:
            path = str(path).strip()
            mat = Material.search([("pdf_path", "=", path), ("company_id", "=", company.id)], limit=1) if path else Material.browse()
            if not mat and path:
                mat = Material.search([("html_source_path", "=", path), ("company_id", "=", company.id)], limit=1)
            if mat:
                materials |= mat
            else:
                log.append("plan %s/%s: unknown material %r" % (date_str, key, path))
        project = Project.browse()
        project_code = str(row.get("project") or "").strip()
        if project_code:
            project = Project._by_code(project_code, company)
            if not project:
                log.append("plan %s/%s: unknown project %r" % (date_str, key, project_code))

        def text(name):
            value = row.get(name)
            return str(value) if value else False

        return {
            "plan_key": key,
            "sequence": int(row.get("sequence", 10 * (index + 1))),
            "kind": row.get("kind") or "bloc",
            "subject_id": subject.id or False,
            "name": str(row["name"]).strip(),
            "duration_planned": int(row.get("duration_planned", 45) or 0),
            "anchored": bool(row.get("anchored")),
            "start_fixed": float(row.get("start_fixed") or 0.0),
            "intention": text("intention"),
            "steps": text("steps"),
            "success": text("success"),
            "fallback": text("fallback"),
            "item_ids": [Command.set(items.ids)],
            "material_ids": [Command.set(materials.ids)],
            "project_id": project.id or False,
        }

    @api.model
    def _plan_deliverable_vals(self, row, index):
        return {
            "plan_key": str(row["key"]).strip(),
            "sequence": int(row.get("sequence", 10 * (index + 1))),
            "when": str(row["when"]).strip() if row.get("when") else False,
            "name": str(row["name"]).strip(),
            "detail": str(row["detail"]) if row.get("detail") else False,
            "bonus": bool(row.get("bonus")),
        }

    @api.model
    def _plan_sync(self, day, records, rows, is_closed, label, make_vals, date_str, log):
        """Match ``rows`` (validated plan rows) to ``records`` (the day's blocks or
        deliverables): by ``plan_key`` first, else a keyless record with the same exact
        ``(kind, name)`` (blocks) / ``name`` (deliverables). An open match is updated in
        place and a closed one left as it is (its key is stamped if it had none, so the next
        replay finds it by key); a row without a match is created; an open record absent
        from the rows is deleted. Returns ``({key: id}, deleted_count)``."""
        by_key = {rec.plan_key: rec for rec in records if rec.plan_key}
        matched = {}
        claimed = records.browse()
        for row in rows:
            key = str(row["key"]).strip()
            rec = by_key.get(key)
            if rec is not None:
                matched[key] = rec
                claimed |= rec
        for row in rows:
            key = str(row["key"]).strip()
            if key in matched:
                continue
            name = str(row["name"]).strip()
            kind = row.get("kind") or "bloc"
            for rec in (records - claimed).filtered(lambda r: not r.plan_key and r.name == name):
                if label == "block" and rec.kind != kind:
                    continue
                matched[key] = rec
                claimed |= rec
                break
        result = {}
        for index, row in enumerate(rows):
            key = str(row["key"]).strip()
            vals = make_vals(row, index)
            rec = matched.get(key)
            if rec is None:
                rec = records.create(dict(vals, day_id=day.id))
            elif is_closed(rec):
                if not rec.plan_key:
                    rec.write({"plan_key": key})
                log.append("plan %s/%s: %s %d already %s, kept" % (date_str, key, label, rec.id, "done" if label == "deliverable" else "closed"))
            else:
                rec.write(vals)
            result[key] = rec.id
        deleted = 0
        for rec in (records - claimed).sorted(lambda r: (r.sequence, r.id)):
            if is_closed(rec):
                continue
            log.append("plan %s/%s: deleted %s %d «%s»" % (
                date_str, rec.plan_key or "-", "planned block" if label == "block" else label, rec.id, rec.name))
            rec.unlink()
            deleted += 1
        return result, deleted

    @api.model
    def log_plan(self, student_id, date, plan):
        """The whole plan of one day, written in one idempotent call — Odoo is the source of
        the plan. ``plan`` is one dict: the day's scalars (``start_time``, ``is_off``,
        ``off_reason``, ``opening``, ``evening_before``, ``debrief``, ``note`` — each written
        only when its key is present), ``blocks`` and ``deliverables`` (lists of dicts, each
        with a stable ``key``; absent → that part of the day is left untouched, ``[]`` → the
        planned lines are removed). A block: ``key, sequence, kind, subject`` (code or csv
        key), ``name, duration_planned, anchored, start_fixed, intention, steps, success,
        fallback, items`` (codes), ``materials`` (repository paths), ``project`` (code). A
        deliverable: ``key, sequence, when, name, detail, bonus``. Replay rules: a block is
        matched by ``plan_key`` (else by exact kind and name when it has no key, then it
        takes the key); a matched block that is still ``planned`` with no actuals is updated
        in place; a closed one (any other status, or actuals recorded) is never overwritten
        and never deleted; planned, actual-less blocks absent from the payload are deleted.
        Same for deliverables with ``done`` as the closed test. ``is_off`` true marks the day
        off and leaves blocks and deliverables alone. Unknown subject / item / material /
        project codes are logged, never raised; a duplicate or missing key is a ``UserError``
        before anything is written. Returns ``{"day_id", "block_ids": {key: id},
        "deliverable_ids": {key: id}, "deleted", "log"}``."""
        student = self._student(student_id)
        d = self._date(date)
        date_str = fields.Date.to_string(d)
        if not isinstance(plan, dict):
            raise UserError(self.env._("Plan %(date)s: the plan must be a JSON object.", date=date_str))
        block_rows = self._plan_rows(plan, "blocks", date_str)
        deliverable_rows = self._plan_rows(plan, "deliverables", date_str)
        log = []
        day = self.env["homeschool.day"]._get_or_create(student, d)
        day_vals = {}
        if "start_time" in plan:
            day_vals["start_time"] = float(plan.get("start_time") or 0.0)
        if "is_off" in plan:
            day_vals["is_off"] = bool(plan.get("is_off"))
        if "off_reason" in plan:
            day_vals["off_reason"] = str(plan["off_reason"]) if plan.get("off_reason") else False
        for name in PLAN_DAY_TEXTS:
            if name in plan:
                day_vals[name] = str(plan[name]) if plan.get(name) else False
        if day_vals:
            day.write(day_vals)
        block_ids, deliverable_ids, deleted = {}, {}, 0
        if not day.is_off:
            if block_rows is not None:
                block_ids, n = self._plan_sync(
                    day, day.block_ids, block_rows,
                    lambda b: b.status != "planned" or b.actuals_recorded or b.adult_recorded,
                    "block", lambda row, i: self._plan_block_vals(student, row, i, date_str, log), date_str, log)
                deleted += n
            if deliverable_rows is not None:
                deliverable_ids, n = self._plan_sync(
                    day, day.deliverable_ids, deliverable_rows, lambda x: x.done,
                    "deliverable", self._plan_deliverable_vals, date_str, log)
                deleted += n
        return {"day_id": day.id, "block_ids": block_ids, "deliverable_ids": deliverable_ids, "deleted": deleted, "log": log}

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
