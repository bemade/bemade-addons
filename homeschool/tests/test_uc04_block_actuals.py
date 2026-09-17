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
   an outside-teacher alias → ressource (aliases are passed by the caller), bonus-st → bonus/ST, journee → a day marked off or a single
   block), ``activity`` → name, minutes → actuals, ``notes`` → note; the row's day is
   created if missing.
"""
from .common import HomeschoolCase


class TestBlockActuals(HomeschoolCase):
    def test_adult_minutes_bounded_by_total(self):
        self.skipTest("pending — TDD")

    def test_blank_adult_is_flagged_not_guessed(self):
        self.skipTest("pending — TDD")

    def test_bonus_block(self):
        self.skipTest("pending — TDD")

    def test_day_journal_state(self):
        self.skipTest("pending — TDD")

    def test_weekly_adult_rollup(self):
        self.skipTest("pending — TDD")

    def test_hours_csv_import(self):
        self.skipTest("pending — TDD")
