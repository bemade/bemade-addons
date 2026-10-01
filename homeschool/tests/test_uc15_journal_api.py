# -*- coding: utf-8 -*-
"""UC-15 — Journal API: the household's journal tool writes the records over RPC.

``homeschool.journal.api`` is a service (AbstractModel, ``@api.model`` methods, callable
through ``POST /json/2/homeschool.journal.api/<method>`` with a manager's API key) that
reuses the importer's row logic, so the CSV ↔ record mapping lives in one place.

Acceptance criteria
-------------------
1. ``log_hours(student_id, date, block, activity, matieres, minutes_total,
   minutes_adult_present, notes="", aliases=None)`` does exactly what one ``hours.csv``
   row does through ``import_hours``: same day, same block (kind/subject from the key,
   ``journee`` marker → day off, an existing block with the same name and kind is updated).
   Logging the fixture rows one by one then exporting yields ``HOURS_CSV`` byte for byte —
   the same text the CSV import round-trips to (UC-11). With no exact match, the row
   **closes the first planned block** of the day with the same kind and subject and no
   actuals yet (lowest sequence first): the activity replaces its title, the actuals and
   ``done`` are written, ``duration_planned`` and ``sequence`` are kept, and the log says
   so; a planned block of another subject is never touched (a new block is created).
2. ``log_note(student_id, date, text)`` classifies the bullet like the week-file import
   (``Ce qui a marché`` → ``went_well``, ``Ce qui a mal été`` → ``went_badly``, anything
   else → a ``- `` bullet in ``notes``) and is append-only: today's entry grows in place;
   on a past day the text lands in ``corrections`` as a dated line and the original text is
   never rewritten. A text holding several ``- `` bullets is one call (a whole day logged
   late is created in one go, like an imported section).
3. ``log_trace(student_id, date, trace_id, title, matieres, pda_ids, diffusion, notes="",
   attachment=None, artifact_path=None)`` does what one ``traces.csv`` row does; the
   attachment (``{"name", "data_b64"}``) becomes an ``ir.attachment`` on the trace, once;
   the trace is ``submitted_by="parent"``, ``validated=True``; an empty ``trace_id`` takes
   the next free ``TR-<date>-<letter>`` code. Exporting yields ``TRACES_CSV``.
4. ``log_indicator(student_id, date, code, value, notes="")`` does what one
   ``indicateurs.csv`` row does (one value per indicator/student/date, updated in place);
   an unknown code or a missing value is a ``UserError``, never a silent skip.
5. ``status(student_id, date)`` → ``{"hours_rows", "adult_missing", "journal_entry",
   "done"}`` with the rule of ``journal.py status``: rows exist, no adult minutes missing,
   a journal entry exists.
6. Managers only: portal users, resource users and plain internal users get
   ``AccessError`` on every method; a manager of another family gets ``AccessError`` on a
   student he cannot read; an unknown student id is a ``UserError``.
7. Several families: what a manager of company B logs for his student lands in company B
   and changes nothing in company A's exports.
"""
import base64
import csv
import io
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase, HOURS_CSV, TRACES_CSV, INDIC_VALUES_CSV

ALIASES = {"teacher": ["ressource", None]}  # as JSON hands it over: a list, not a tuple


def _rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def _minutes(cell):
    return int(cell) if (cell or "").strip() else None


class TestJournalAPI(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.manager = self.manager_user()
        self.api = self.env["homeschool.journal.api"].with_user(self.manager)
        self.Exporter = self.env["homeschool.exporter"]
        self.Journal = self.env["homeschool.journal"]
        self.today = fields.Date.context_today(self.Day)

    def _log_hours_fixture(self, api=None, student=None):
        api = api or self.api
        student = student or self.student
        results = []
        for r in _rows(HOURS_CSV):
            results.append(api.log_hours(
                student.id, r["date"], r["block"], r["activity"], r["matieres"],
                _minutes(r["minutes_total"]), _minutes(r["minutes_adult_present"]),
                notes=r["notes"], aliases=ALIASES,
            ))
        return results

    # ------------------------------------------------------------------
    # 1. log_hours
    # ------------------------------------------------------------------
    def test_log_hours_equals_the_csv_import(self):
        results = self._log_hours_fixture()
        self.assertEqual(self.Exporter.export_hours(self.student), HOURS_CSV)
        texts = self.Exporter.with_user(self.manager).export_texts(self.student.id, files=["tracking/hours.csv"])
        self.assertEqual(texts["tracking/hours.csv"], HOURS_CSV, "export_texts sees the same rows")
        first = results[0]
        self.assertEqual(set(first), {"day_id", "block_id", "log"})
        block = self.Block.browse(first["block_id"])
        self.assertEqual((block.kind, block.subject_id, block.name, block.minutes_total, block.minutes_adult_present),
                         ("bloc", self.fle, "Segment 1 French", 45, 45))
        self.assertEqual(block.day_id.id, first["day_id"])
        self.assertEqual(block.company_id, self.company)
        off = results[4]  # 2026-01-07,journee,No school today,,0,0,day off
        self.assertIsNone(off["block_id"], "a day-off marker creates no block")
        day_off = self.Day.browse(off["day_id"])
        self.assertTrue(day_off.is_off)
        self.assertEqual((day_off.off_reason, day_off.note), ("No school today", "day off"))
        teacher = results[5]
        self.assertEqual(self.Block.browse(teacher["block_id"]).kind, "ressource", "aliases apply as in the importer")
        self.assertEqual(self.Block.browse(results[2]["block_id"]).kind, "reading")
        self.assertEqual(self.Block.browse(results[3]["block_id"]).kind, "bonus")
        self.assertFalse(any(r["log"] for r in results), "no unknown subject in the fixture")

    def test_log_hours_updates_the_same_block(self):
        d = "2026-03-02"
        a = self.api.log_hours(self.student.id, d, "bloc-fle", "Segment 1 French", "FLE", 45, None)
        b = self.api.log_hours(self.student.id, d, "bloc-fle", "Segment 1 French", "FLE", 50, 45, notes="fixed later")
        self.assertEqual(a["block_id"], b["block_id"], "same name and kind: the block is updated, not duplicated")
        self.assertEqual(a["day_id"], b["day_id"])
        block = self.Block.browse(b["block_id"])
        self.assertEqual((block.minutes_total, block.minutes_adult_present, block.note), (50, 45, "fixed later"))
        self.assertEqual(self.Day.browse(a["day_id"]).block_count, 1)
        c = self.api.log_hours(self.student.id, d, "bloc-zzz", "Mystery", "", 10, 10)
        self.assertIn("unknown subject 'zzz'", c["log"][0], "the importer's log is returned to the caller")
        self.assertFalse(self.Block.browse(c["block_id"]).subject_id)
        self.assertFalse(self.env["homeschool.subject"].with_context(active_test=False).search([("code", "=", "ZZZ")]),
                         "never creates a subject")
        matieres_as_list = self.api.log_hours(self.student.id, d, "projets", "Kite", ["ST", "MATH"], 30, 30)
        block = self.Block.browse(matieres_as_list["block_id"])
        self.assertEqual((block.kind, block.subject_id, block.subject_codes), ("projects", self.st, "ST;MATH"))

    def test_log_hours_closes_the_planned_block(self):
        day = self.make_day(self.today)
        opening = self.make_block(day, "Opening", 10, 1, kind="opening")
        planned = self.make_block(day, "P1 Math — fractions", 45, 2, subject_id=self.math.id,
                                  intention="fractions on the number line")
        r = self.api.log_hours(self.student.id, self.today, "bloc-math", "Fractions, number line", "MATH", 50, 45)
        self.assertEqual(r["block_id"], planned.id, "the planned MATH block is closed, not duplicated")
        self.assertEqual(day.block_count, 2)
        self.assertEqual((planned.name, planned.status, planned.minutes_total, planned.minutes_adult_present),
                         ("Fractions, number line", "done", 50, 45), "the activity replaces the title")
        self.assertEqual((planned.duration_planned, planned.sequence), (45, 2), "the plan is the plan")
        self.assertEqual(planned.intention, "fractions on the number line")
        self.assertEqual((planned.csv_key, planned.subject_codes), ("bloc-math", "MATH"))
        self.assertEqual(r["log"], ["hours.csv %s/bloc-math: closed planned block %d «P1 Math — fractions»"
                                    % (fields.Date.to_string(self.today), planned.id)])
        self.assertEqual(opening.status, "planned", "another kind is never touched")
        # the block is no longer planned: the same key with yet another text creates a new block
        r2 = self.api.log_hours(self.student.id, self.today, "bloc-math", "Fractions again", "MATH", 20, 20)
        self.assertNotEqual(r2["block_id"], planned.id)
        self.assertEqual(day.block_count, 3)
        self.assertEqual(r2["log"], [])

    def test_log_hours_closes_planned_blocks_in_sequence(self):
        day = self.make_day(self.today)
        second = self.make_block(day, "P2 Math", 30, 5, subject_id=self.math.id)
        first = self.make_block(day, "P1 Math", 45, 2, subject_id=self.math.id)
        a = self.api.log_hours(self.student.id, self.today, "bloc-math", "Geometry", "MATH", 45, 45)
        self.assertEqual(a["block_id"], first.id, "the lowest sequence is closed first")
        self.assertEqual(second.status, "planned")
        b = self.api.log_hours(self.student.id, self.today, "bloc-math", "Mental math", "MATH", 30, 30)
        self.assertEqual(b["block_id"], second.id, "the next call closes the next one")
        self.assertEqual((second.name, second.status, second.sequence), ("Mental math", "done", 5))
        self.assertEqual(day.block_count, 2)

    def test_log_hours_never_closes_another_subject(self):
        day = self.make_day(self.today)
        planned_fle = self.make_block(day, "P1 French", 45, 1, subject_id=self.fle.id)
        r = self.api.log_hours(self.student.id, self.today, "bloc-math", "Fractions", "MATH", 50, 45)
        self.assertNotEqual(r["block_id"], planned_fle.id)
        self.assertEqual((planned_fle.name, planned_fle.status), ("P1 French", "planned"))
        self.assertEqual(day.block_count, 2, "a new block is created")
        self.assertEqual(r["log"], [])
        # a planned block already holding actuals is not a candidate either
        done_math = self.make_block(day, "P2 Math", 45, 3, subject_id=self.math.id, minutes_total=45)
        r2 = self.api.log_hours(self.student.id, self.today, "bloc-math", "More math", "MATH", 10, 10)
        self.assertNotEqual(r2["block_id"], done_math.id)
        self.assertEqual(done_math.minutes_total, 45)
        # subject-less key and subject-less planned block: they match
        bonus = self.make_block(day, "Free project time", 30, 9, kind="projects")
        r3 = self.api.log_hours(self.student.id, self.today, "projets", "Kite", "", 30, 30)
        self.assertEqual(r3["block_id"], bonus.id)
        self.assertEqual(bonus.name, "Kite")

    def test_log_hours_exact_name_wins_over_the_fallback(self):
        day = self.make_day(self.today)
        planned = self.make_block(day, "P1 Math", 45, 1, subject_id=self.math.id)
        exact = self.make_block(day, "Segment 2 Math", 45, 2, subject_id=self.math.id, minutes_total=40, minutes_adult_present=40, status="done")
        r = self.api.log_hours(self.student.id, self.today, "bloc-math", "Segment 2 Math", "MATH", 45, 45)
        self.assertEqual(r["block_id"], exact.id, "same name and kind: updated in place, the planned block is left alone")
        self.assertEqual((exact.minutes_total, exact.minutes_adult_present), (45, 45))
        self.assertEqual((planned.name, planned.status), ("P1 Math", "planned"))
        self.assertEqual(day.block_count, 2)
        self.assertEqual(r["log"], [])

    # ------------------------------------------------------------------
    # 2. log_note
    # ------------------------------------------------------------------
    def test_log_note_today_classifies_like_the_import(self):
        imported = self.env["homeschool.importer"].import_journal(self.repo, self.student)
        jan5 = self.Journal.search([("student_id", "=", self.student.id), ("date", "=", date(2026, 1, 5))])
        # the same three bullets as the fixture's 2026-01-05 section, one call each, today
        r1 = self.api.log_note(self.student.id, self.today, "Ce qui a marché : French went fine.")
        r2 = self.api.log_note(self.student.id, self.today, "Ce qui a mal été : Math ended in a fight.")
        r3 = self.api.log_note(self.student.id, self.today, "Indicateurs du jour : R3-CONFLITS 1.")
        self.assertEqual(r1["journal_id"], r2["journal_id"])
        self.assertEqual(r1["journal_id"], r3["journal_id"], "one entry per day")
        entry = self.Journal.browse(r1["journal_id"])
        self.assertEqual(entry.date, self.today)
        self.assertEqual((entry.went_well, entry.went_badly, entry.notes), (jan5.went_well, jan5.went_badly, jan5.notes),
                         "the API classifies exactly like the week-file import")
        self.assertFalse(entry.corrections)
        self.assertFalse(r1["corrected"])
        self.api.log_note(self.student.id, self.today, "Ce qui a marché : reading too.")
        self.assertEqual(entry.went_well, "French went fine.\nreading too.", "append-only, in place today")
        self.api.log_note(self.student.id, self.today, "a plain remark")
        self.assertEqual(entry.notes, "- Indicateurs du jour : R3-CONFLITS 1.\n- a plain remark")
        self.assertEqual(self.Journal.search_count([("student_id", "=", self.student.id), ("date", "=", self.today)]), 1)

    def test_log_note_past_day_lands_in_corrections(self):
        past = self.today - timedelta(days=3)
        day = self.make_day(past)
        entry = self.Journal.create({"day_id": day.id, "went_well": "original", "notes": "- kept"})
        r = self.api.log_note(self.student.id, past, "Ce qui a marché : rewritten")
        self.assertEqual(r["journal_id"], entry.id)
        self.assertTrue(r["corrected"])
        self.assertEqual(entry.went_well, "original", "past text is never rewritten")
        self.assertEqual(entry.notes, "- kept")
        self.assertIn(fields.Date.to_string(self.today), entry.corrections)
        self.assertIn("rewritten", entry.corrections)
        self.api.log_note(self.student.id, past, "late remark")
        self.assertEqual(entry.notes, "- kept")
        self.assertIn("- late remark", entry.corrections)
        # a past day without any entry yet: the first text creates the entry (nothing to correct)
        older = past - timedelta(days=1)
        r = self.api.log_note(self.student.id, older, "- Ce qui a marché : logged late\n- Ce qui a mal été : nothing\n- R3 0")
        late = self.Journal.browse(r["journal_id"])
        self.assertEqual((late.date, late.went_well, late.went_badly, late.notes), (older, "logged late", "nothing", "- R3 0"))
        self.assertFalse(late.corrections)
        self.assertFalse(r["corrected"])
        self.assertEqual(self.Day.search_count([("student_id", "=", self.student.id), ("date", "=", older)]), 1, "the day was created")

    # ------------------------------------------------------------------
    # 3. log_trace
    # ------------------------------------------------------------------
    def test_log_trace_equals_the_csv_import(self):
        self.env["homeschool.importer"].import_curriculum(self.repo)
        pdf = b"%PDF-1.4 fake\n"
        results = []
        for r in _rows(TRACES_CSV):
            attachment = None
            if r["artifact_path"]:
                attachment = {"name": r["artifact_path"].rsplit("/", 1)[-1], "data_b64": base64.b64encode(pdf).decode()}
            results.append(self.api.log_trace(
                self.student.id, r["date"], r["trace_id"], r["title"], r["matieres"], r["pda_ids"], r["diffusion"],
                notes=r["notes"], attachment=attachment, artifact_path=r["artifact_path"] or None,
            ))
        self.assertEqual(self.Exporter.export_traces(self.student), TRACES_CSV)
        a = self.Trace.browse(results[0]["trace_id"])
        self.assertEqual(a, self.env.ref("homeschool.trace_TR_2026_01_05_a"), "the external id is kept, like the importer")
        self.assertEqual((a.code, a.date, a.subject_ids, a.diffusion, a.note), ("TR-2026-01-05-a", date(2026, 1, 5), self.math, "internal", "note one"))
        self.assertEqual(sorted(a.item_ids.mapped("code")), ["FLE-E-SYN-C-E.2.a.i", "MATH-MES-G.1"])
        self.assertEqual((a.submitted_by, a.validated), ("parent", True))
        self.assertEqual(a.attachment_ids.mapped("name"), ["TR-2026-01-05-a.pdf"])
        self.assertEqual(a.attachment_ids.raw, pdf)
        self.assertEqual(a.attachment_ids.res_model, "homeschool.trace")
        self.assertEqual(a.artifact_path, "tracking/traces/TR-2026-01-05-a.pdf")
        self.assertEqual(results[0]["log"], [])
        b = self.Trace.browse(results[1]["trace_id"])
        self.assertEqual((b.diffusion, b.item_ids.mapped("code"), b.attachment_ids), ("institutional", ["US-C1-1820"], self.env["ir.attachment"]))
        # the same call again: updated in place, no second attachment
        again = self.api.log_trace(self.student.id, "2026-01-05", "TR-2026-01-05-a", "First trace", "MATH",
                                   ["MATH-MES-G.1", "FLE-E-SYN-C-E.2.a.i"], "INTERNAL", notes="note one",
                                   attachment={"name": "TR-2026-01-05-a.pdf", "data_b64": base64.b64encode(pdf).decode()})
        self.assertEqual(again["trace_id"], a.id)
        self.assertEqual(len(a.attachment_ids), 1)
        self.assertEqual(self.Trace.search_count([("student_id", "=", self.student.id)]), 2)
        # no trace id: the next free code of that day, as the trace form would give
        r = self.api.log_trace(self.student.id, "2026-01-05", "", "Third", "FLE", "", "internal")
        self.assertEqual(self.Trace.browse(r["trace_id"]).code, "TR-2026-01-05-c")
        r = self.api.log_trace(self.student.id, "2026-01-06", None, "Unknown item", "US", "NOPE-9", "INTERNAL")
        self.assertIn("unknown item 'NOPE-9'", r["log"][0])

    # ------------------------------------------------------------------
    # 4. log_indicator
    # ------------------------------------------------------------------
    def test_log_indicator_equals_the_csv_import(self):
        self.env["homeschool.importer"].import_indicators(self.repo, self.student)
        r = self.api.log_indicator(self.student.id, "2026-01-16", "K1-ENGAGE", 3, notes="three of four")
        value = self.env["homeschool.indicator.value"].browse(r["value_id"])
        self.assertEqual((value.code, value.date, value.value, value.note, value.student_id, value.company_id),
                         ("K1-ENGAGE", date(2026, 1, 16), 3.0, "three of four", self.student, self.company))
        self.assertTrue(r["created"])
        self.assertEqual(self.Exporter.export_indicator_values(self.student),
                         INDIC_VALUES_CSV + "2026-01-16,K1-ENGAGE,3,three of four\n")
        r2 = self.api.log_indicator(self.student.id, "2026-01-16", "K1-ENGAGE", "2,5")
        self.assertEqual(r2["value_id"], value.id, "one value per indicator, student and date: updated in place")
        self.assertFalse(r2["created"])
        self.assertEqual((value.value, value.note), (2.5, False))
        self.assertEqual(self.Exporter.export_indicator_values(self.student),
                         INDIC_VALUES_CSV + "2026-01-16,K1-ENGAGE,2.5,\n")
        with self.assertRaises(UserError):
            self.api.log_indicator(self.student.id, "2026-01-16", "NOPE", 1)
        with self.assertRaises(UserError):
            self.api.log_indicator(self.student.id, "2026-01-16", "K1-ENGAGE", None)
        with self.assertRaises(UserError):
            self.api.log_indicator(self.student.id, "2026-01-16", "K1-ENGAGE", "")

    # ------------------------------------------------------------------
    # 5. status
    # ------------------------------------------------------------------
    def test_status_transitions(self):
        d = "2026-03-09"
        empty = {"hours_rows": 0, "adult_missing": 0, "journal_entry": False, "done": False}
        self.assertEqual({k: self.api.status(self.student.id, d)[k] for k in empty}, empty)
        self.assertIsNone(self.api.status(self.student.id, d)["day_id"])
        self.api.log_hours(self.student.id, d, "bloc-fle", "Segment 1 French", "FLE", 45, None)
        self.api.log_hours(self.student.id, d, "bloc-math", "Segment 2 Math", "MATH", 45, 30)
        s = self.api.status(self.student.id, d)
        self.assertEqual((s["hours_rows"], s["adult_missing"], s["journal_entry"], s["done"]), (2, 1, False, False))
        self.api.log_hours(self.student.id, d, "bloc-fle", "Segment 1 French", "FLE", 45, 45)
        s = self.api.status(self.student.id, d)
        self.assertEqual((s["hours_rows"], s["adult_missing"], s["journal_entry"], s["done"]), (2, 0, False, False))
        self.api.log_note(self.student.id, d, "Ce qui a marché : all of it")
        s = self.api.status(self.student.id, d)
        self.assertEqual((s["hours_rows"], s["adult_missing"], s["journal_entry"], s["done"]), (2, 0, True, True))
        self.assertEqual(s["day_id"], self.Day.search([("student_id", "=", self.student.id), ("date", "=", date(2026, 3, 9))]).id)
        # a day off counts its marker row, like hours.csv does
        off = "2026-03-10"
        self.api.log_hours(self.student.id, off, "journee", "Holiday", "", 0, 0)
        s = self.api.status(self.student.id, off)
        self.assertEqual((s["hours_rows"], s["adult_missing"], s["journal_entry"], s["done"]), (1, 0, False, False))
        self.api.log_note(self.student.id, off, "slept in")
        self.assertTrue(self.api.status(self.student.id, off)["done"])
        # a journal entry alone is not a logged day
        alone = "2026-03-11"
        self.api.log_note(self.student.id, alone, "nothing recorded")
        s = self.api.status(self.student.id, alone)
        self.assertEqual((s["hours_rows"], s["journal_entry"], s["done"]), (0, True, False))

    # ------------------------------------------------------------------
    # 6. access
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_managers_only(self):
        portal = self.portal_user()
        self.student.user_id = portal
        teacher = self.resource_user(self.student)
        plain = self.internal_user()
        Api = self.env["homeschool.journal.api"]
        calls = [
            ("log_hours", (self.student.id, "2026-03-02", "bloc-fle", "x", "FLE", 10, 10)),
            ("log_note", (self.student.id, "2026-03-02", "x")),
            ("log_trace", (self.student.id, "2026-03-02", "", "x", "FLE", "", "INTERNAL")),
            ("log_indicator", (self.student.id, "2026-03-02", "R3-CONFLITS", 1)),
            ("status", (self.student.id, "2026-03-02")),
        ]
        for user in (portal, teacher, plain):
            for method, args in calls:
                with self.assertRaises(AccessError, msg="%s / %s" % (user.login, method)):
                    getattr(Api.with_user(user), method)(*args)
        self.assertFalse(self.Day.search([("student_id", "=", self.student.id)]), "nothing was written")
        # a manager of another family: AccessError on a student he cannot read
        manager_b = self.manager_user(self.company_b, login="hs_manager_b")
        for method, args in calls:
            with self.assertRaises(AccessError, msg=method):
                getattr(Api.with_user(manager_b), method)(*args)
        with self.assertRaises(UserError):
            self.api.status(self.student.id + 999999, "2026-03-02")
        with self.assertRaises(UserError):
            self.api.log_note(self.student.id + 999999, "2026-03-02", "x")

    # ------------------------------------------------------------------
    # 7. several families
    # ------------------------------------------------------------------
    def test_second_family_untouched(self):
        imp = self.env["homeschool.importer"]
        imp.import_curriculum(self.repo)
        imp.import_indicators(self.repo, self.student)
        self._log_hours_fixture()
        hours_a = self.Exporter.export_hours(self.student)
        traces_a = self.Exporter.export_traces(self.student)
        values_a = self.Exporter.export_indicator_values(self.student)
        manager_b = self.manager_user(self.company_b, login="hs_manager_b")
        api_b = self.env["homeschool.journal.api"].with_user(manager_b)
        imp.import_indicators(self.repo, self.student_b)
        d = "2026-02-02"
        h = api_b.log_hours(self.student_b.id, d, "bloc-fle", "Other French", "FLE", 30, 30)
        n = api_b.log_note(self.student_b.id, d, "Ce qui a marché : fine")
        t = api_b.log_trace(self.student_b.id, d, "TR-2026-02-02-a", "Other trace", "FLE", "FLE-E-SYN-C-E", "INSTITUTIONAL")
        v = api_b.log_indicator(self.student_b.id, d, "R3-CONFLITS", 2)
        s = api_b.status(self.student_b.id, d)
        self.assertEqual((s["hours_rows"], s["adult_missing"], s["journal_entry"], s["done"]), (1, 0, True, True))
        for model, res in (("homeschool.day", h["day_id"]), ("homeschool.block", h["block_id"]), ("homeschool.journal", n["journal_id"]),
                           ("homeschool.trace", t["trace_id"]), ("homeschool.indicator.value", v["value_id"])):
            rec = self.env[model].browse(res)
            self.assertEqual(rec.company_id, self.company_b, model)
            self.assertEqual(rec.student_id, self.student_b, model)
        # company A's files are exactly what they were
        self.assertEqual(self.Exporter.export_hours(self.student), hours_a)
        self.assertEqual(self.Exporter.export_traces(self.student), traces_a)
        self.assertEqual(self.Exporter.export_indicator_values(self.student), values_a)
        self.assertEqual(self.Exporter.export_hours(self.student_b).splitlines()[1:], ["2026-02-02,bloc-fle,Other French,FLE,30,30,"])
        self.assertEqual(self.Exporter.export_traces(self.student_b).splitlines()[1:],
                         ["TR-2026-02-02-a,2026-02-02,Other trace,FLE,FLE-E-SYN-C-E,,INSTITUTIONAL,"])
        self.assertEqual(self.Exporter.export_indicator_values(self.student_b).splitlines()[1:],
                         ["2026-01-09,R3-CONFLITS,1,one event", "2026-02-02,R3-CONFLITS,2,"],
                         "B's own fixture value (import_indicators) and the logged one, nothing of A")
        # the same trace code in two families are two traces with two external ids
        self.api.log_trace(self.student.id, d, "TR-2026-02-02-a", "A's trace", "FLE", "", "INTERNAL")
        self.assertEqual(self.Trace.search_count([("code", "=", "TR-2026-02-02-a")]), 2)
        self.assertEqual(self.Exporter.export_traces(self.student_b).splitlines()[1:],
                         ["TR-2026-02-02-a,2026-02-02,Other trace,FLE,FLE-E-SYN-C-E,,INSTITUTIONAL,"])
