# -*- coding: utf-8 -*-
"""UC-03 — Weekday templates generate a week from the household grid.

Acceptance criteria
-------------------
1. A ``homeschool.block.template`` has weekday, sequence, kind, subject, duration,
   optional ``start_fixed``, default name; templates are per student (and year).
2. The École Felix grid is shipped as data: Mon/Tue opening 5 + bloc 45 + pause 15 +
   bloc 45 + pause 15 + bloc 35 + debrief 15, reading 20 fixed at 14:00; Wed projects
   9–12 + reading; Thu ressource (Josée 9–11) *or* bloc — the template carries an
   ``alternative`` flag; Fri none.
3. "Generate week" for an ISO week creates days and blocks from the templates;
   running it again does **not** duplicate (days already holding blocks are skipped
   and reported); a holiday (``homeschool.day`` with ``is_off``) gets no blocks.
4. Generated blocks have ``status = planned`` and empty actual minutes.
5. The generated week matches the current ``/journal`` grid used to pre-fill hours
   (Mon/Tue bloc 9–12 · reading 14:00; Wed projects · reading; Thu Josée or bloc ·
   reading; Fri none).
"""
from .common import HomeschoolCase


class TestWeekTemplates(HomeschoolCase):
    def test_grid_data_present(self):
        self.skipTest("pending — TDD")

    def test_generate_week(self):
        self.skipTest("pending — TDD")

    def test_generate_twice_no_duplicates(self):
        self.skipTest("pending — TDD")

    def test_day_off_skipped(self):
        self.skipTest("pending — TDD")
