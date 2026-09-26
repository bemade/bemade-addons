# -*- coding: utf-8 -*-
"""UC-08 — The parent's journal: blunt, daily, never in a portal.

Acceptance criteria
-------------------
1. ``homeschool.journal`` has ``day_id`` (unique per day), ``went_well``,
   ``went_badly``, ``notes`` (Markdown), ``indicator_notes`` (free text: conflicts,
   withdrawal, spontaneous engagement, recovery delay — tallied on Sunday), and
   ``corrections`` (dated appended text — past entries are never edited in place:
   writing to a past day's fields appends a dated correction instead).
2. It is a separate model from the day, with **no** portal access rule and no
   ``ir.model.access`` line for portal groups; a portal user reading it raises
   AccessError even by direct id.
3. Importing the week files (``tracking/journal/YYYY-Www/YYYY-Www.md``, ``### DATE``
   sections) creates entries with the bullet notes preserved verbatim.
4. The child's comments on traces stay on the trace (``student_comment``), never in
   the journal (UC-05).
"""
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase


class TestJournal(HomeschoolCase):
    @mute_logger("odoo.sql_db")
    def test_one_entry_per_day(self):
        day = self.make_day(fields.Date.context_today(self.Day))
        Journal = self.env["homeschool.journal"]
        entry = Journal.create({"day_id": day.id, "went_well": "fine"})
        self.assertEqual(entry.date, day.date)
        self.assertEqual(entry.student_id, self.student)
        with self.assertRaises(Exception):
            Journal.create({"day_id": day.id, "went_well": "again"})
        entry.append_note("went_badly", "math fight")
        entry.append_note("went_badly", "and again")
        self.assertEqual(entry.went_badly, "math fight\nand again")
        self.assertFalse(entry.corrections, "today's entry is edited in place")

    def test_past_entries_append_corrections(self):
        today = fields.Date.context_today(self.Day)
        day = self.make_day(today - timedelta(days=3))
        entry = self.env["homeschool.journal"].create({"day_id": day.id, "went_well": "original", "went_badly": "bad"})
        entry.write({"went_well": "rewritten", "indicator_notes": "R3 1"})
        self.assertEqual(entry.went_well, "original", "past entries are never edited in place")
        self.assertIn(fields.Date.to_string(today), entry.corrections)
        self.assertIn("rewritten", entry.corrections)
        self.assertIn("R3 1", entry.corrections)
        entry.write({"notes": "a note today"})  # non-frozen fields? notes is frozen too
        self.assertFalse(entry.notes)
        self.assertIn("a note today", entry.corrections)
        entry.with_context(journal_force_edit=True).write({"went_well": "import"})
        self.assertEqual(entry.went_well, "import", "the importer may write in place")

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_no_portal_access(self):
        day = self.make_day(fields.Date.context_today(self.Day))
        entry = self.env["homeschool.journal"].create({"day_id": day.id, "went_well": "secret"})
        portal = self.portal_user()
        self.student.user_id = portal
        with self.assertRaises(AccessError):
            entry.with_user(portal).read(["went_well"])
        with self.assertRaises(AccessError):
            self.env["homeschool.journal"].with_user(portal).search([])
        self.assertFalse(self.env["ir.rule"].search([("model_id.model", "=", "homeschool.journal")]), "no rule at all")
        self.assertFalse(self.env["ir.model.access"].search([("model_id.model", "=", "homeschool.journal"), ("group_id", "=", self.env.ref("base.group_portal").id)]))

    def test_week_file_import(self):
        log = self.env["homeschool.importer"].import_journal(self.repo, self.student)
        Journal = self.env["homeschool.journal"]
        jan5 = Journal.search([("student_id", "=", self.student.id), ("date", "=", date(2026, 1, 5))])
        self.assertEqual(jan5.went_well, "French went fine.")
        self.assertEqual(jan5.went_badly, "Math ended in a fight.")
        self.assertEqual(jan5.notes, "- Indicateurs du jour : R3-CONFLITS 1.")
        jan6 = Journal.search([("student_id", "=", self.student.id), ("date", "=", date(2026, 1, 6))])
        self.assertEqual(jan6.went_well, "bonus science.")
        self.assertFalse(jan6.went_badly)
        self.env["homeschool.importer"].import_journal(self.repo, self.student)
        self.assertEqual(Journal.search_count([("student_id", "=", self.student.id)]), 2, "idempotent")
        self.assertEqual(jan5.went_well, "French went fine.")
        self.assertFalse(jan5.corrections, "the importer writes in place, no correction noise")
