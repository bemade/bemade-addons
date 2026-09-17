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
from .common import HomeschoolCase


class TestJournal(HomeschoolCase):
    def test_one_entry_per_day(self):
        self.skipTest("pending — TDD")

    def test_past_entries_append_corrections(self):
        self.skipTest("pending — TDD")

    def test_no_portal_access(self):
        self.skipTest("pending — TDD")

    def test_week_file_import(self):
        self.skipTest("pending — TDD")
