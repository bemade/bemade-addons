# -*- coding: utf-8 -*-
"""UC-04 — Actual minutes live on the block; the day cannot close on a guess.

Acceptance criteria
-------------------
1. A block carries ``minutes_total`` and ``minutes_adult_present`` (integers, blank
   allowed) and ``status`` in planned | done | partial | skipped.
2. ``minutes_adult_present`` cannot exceed ``minutes_total``; both blank is "not
   recorded", a blank adult with a filled total is allowed but flagged (a blank is
   honest; a guess is not).
3. A **bonus** block (unplanned session, an unplanned science session, say) is
   created at journal time with kind ``bonus``, its minutes, subject and note.
4. ``homeschool.day.journal_state`` is computed: ``incomplete`` when any non-pause,
   non-skipped block of a past or current day lacks ``minutes_total``, or when the
   day has no journal entry; ``done`` otherwise. (Replaces ``journal.py status``.)
5. The weekly adult-presence rollup (sum of ``minutes_adult_present`` per ISO week,
   in hours) is available through ``read_group`` and equals what
   ``report.py hours`` computes from ``hours.csv`` for the same rows.
6. Importing ``tracking/hours.csv`` maps each row to a block: ``block`` column →
   kind + subject (bloc-fle → bloc/FLE, lecture → reading, projets → projects,
   an outside-teacher alias → ressource (aliases are passed by the caller), bonus-st → bonus/ST,
   journee → a day marked off or a single block), ``activity`` → name, minutes →
   actuals, ``notes`` → note; the row's day is created if missing.
"""
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase


class TestBlockActuals(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.context_today(self.Day)
        self.day = self.make_day(self.today)
        self.s1 = self.make_block(self.day, "Segment 1", 45, 1, subject_id=self.fle.id)
        self.pause = self.make_block(self.day, "Pause", 15, 2, kind="pause")
        self.s2 = self.make_block(self.day, "Segment 2", 45, 3, subject_id=self.math.id)

    @mute_logger("odoo.sql_db")
    def test_adult_minutes_bounded_by_total(self):
        with self.assertRaises(ValidationError):
            self.s1.write({"minutes_total": 30, "minutes_adult_present": 45})
        self.s1.write({"minutes_total": 45, "minutes_adult_present": 45})
        self.assertTrue(self.s1.actuals_recorded)
        self.assertTrue(self.s1.adult_recorded)

    def test_blank_adult_is_flagged_not_guessed(self):
        self.assertFalse(self.s1.actuals_recorded)
        self.assertFalse(self.s1.adult_missing, "nothing recorded yet: nothing to flag")
        self.s1.write({"minutes_total": 45})
        self.assertTrue(self.s1.actuals_recorded)
        self.assertFalse(self.s1.adult_recorded)
        self.assertTrue(self.s1.adult_missing, "total without adult minutes = honest blank, flagged")
        self.assertEqual(self.s1.minutes_adult_present, 0, "but never a guessed number")
        self.s1.write({"minutes_adult_present": 0})
        self.assertTrue(self.s1.adult_recorded, "an explicit zero is a recorded value")
        self.assertFalse(self.s1.adult_missing)

    def test_bonus_block(self):
        bonus = self.make_block(self.day, "Unplanned science session", 30, 9, kind="bonus", subject_id=self.st.id,
                                minutes_total=30, minutes_adult_present=30, status="done", note="spontaneous")
        self.assertEqual(bonus.kind, "bonus")
        self.assertTrue(bonus.actuals_recorded and bonus.adult_recorded)
        self.assertEqual(self.day.actual_minutes, 30)
        self.assertEqual(self.day.adult_minutes, 30)

    def test_day_journal_state(self):
        self.assertEqual(self.day.journal_state, "incomplete")
        self.s1.write({"minutes_total": 45, "minutes_adult_present": 45})
        self.s2.write({"status": "skipped"})
        self.assertEqual(self.day.journal_state, "incomplete", "no journal entry yet")
        self.env["homeschool.journal"].create({"day_id": self.day.id, "went_well": "fine"})
        self.assertEqual(self.day.journal_state, "done", "pauses and skipped blocks do not block the day")
        future = self.make_day(self.today + timedelta(days=30))
        self.assertEqual(future.journal_state, "future")
        off = self.make_day(self.today - timedelta(days=1), is_off=True)
        self.assertEqual(off.journal_state, "off")

    def test_weekly_adult_rollup(self):
        monday = date(2026, 1, 12)
        d1 = self.make_day(monday)
        d2 = self.make_day(monday + timedelta(days=1))
        self.make_block(d1, "A", 45, 1, minutes_total=45, minutes_adult_present=45)
        self.make_block(d1, "B", 20, 2, kind="reading", minutes_total=20, minutes_adult_present=0)
        self.make_block(d2, "C", 60, 1, minutes_total=60, minutes_adult_present=30)
        hours = self.env["homeschool.indicator"].adult_hours_for_week(self.student, monday + timedelta(days=3))
        self.assertAlmostEqual(hours, 1.25)
        groups = self.Block._read_group([("student_id", "=", self.student.id), ("date", ">=", monday), ("date", "<=", monday + timedelta(days=6))],
                                        ["day_id"], ["minutes_adult_present:sum"])
        self.assertEqual(sorted(m for _, m in groups), [30, 45])

    def test_hours_csv_import(self):
        log = self.env["homeschool.importer"].import_hours(self.repo, self.student, aliases={"teacher": ("ressource", None)})
        self.assertTrue(any("hours.csv" in line for line in log))
        jan5 = self.Day.search([("student_id", "=", self.student.id), ("date", "=", date(2026, 1, 5))])
        self.assertEqual(len(jan5.block_ids), 3)
        fle = jan5.block_ids.filtered(lambda b: b.subject_id == self.fle and b.kind == "bloc")
        self.assertEqual(fle.name, "Segment 1 French")
        self.assertEqual((fle.minutes_total, fle.minutes_adult_present), (45, 45))
        self.assertEqual(fle.status, "done")
        reading = jan5.block_ids.filtered(lambda b: b.kind == "reading")
        self.assertEqual((reading.minutes_total, reading.minutes_adult_present), (20, 0))
        self.assertTrue(reading.adult_recorded)
        jan6 = self.Day.search([("student_id", "=", self.student.id), ("date", "=", date(2026, 1, 6))])
        self.assertEqual(jan6.block_ids.mapped("kind"), ["bonus"])
        self.assertEqual(jan6.block_ids.subject_id, self.st)
        self.assertEqual(jan6.block_ids.note, "spontaneous")
        jan7 = self.Day.search([("student_id", "=", self.student.id), ("date", "=", date(2026, 1, 7))])
        self.assertTrue(jan7.is_off)
        self.assertFalse(jan7.block_ids)
        jan8 = self.Day.search([("student_id", "=", self.student.id), ("date", "=", date(2026, 1, 8))])
        self.assertEqual(jan8.block_ids.mapped("kind"), ["ressource"])
        # idempotent
        self.env["homeschool.importer"].import_hours(self.repo, self.student, aliases={"teacher": ("ressource", None)})
        self.assertEqual(len(jan5.block_ids), 3)
