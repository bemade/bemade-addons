# -*- coding: utf-8 -*-
"""UC-08 — Goals: daily, weekly, monthly. No streaks.

Acceptance criteria
-------------------
1. ``homeschool.practice.goal``: per learner, ``period`` (``day`` | ``week`` |
   ``month``), ``target`` and ``measure`` (``day``: quests done that day; ``week`` and
   ``month``: days whose daily goal was reached; only the learner's practice days count toward a week or month), ``active``.
   Defaults: day = 2 of the 3 quests; week = 3 daily goals; month = 12 daily goals.
2. ``homeschool.practice.goal.achievement``: one per goal and period (unique), with
   ``period_start``, ``achieved_at``. Achieving creates it once (idempotent), at the
   moment the measure reaches the target.
3. **No streaks:** weekly and monthly measures count days, never consecutive days; a
   day without practice resets nothing. No field, label or message says « streak »
   or « série ».
4. A week runs Monday–Sunday and a month by calendar month, in the family's timezone.
5. Changing a target applies from the next period; past achievements are untouched.
"""
from odoo.addons.homeschool.tests.common import HomeschoolCase


class TestGoals(HomeschoolCase):
    pass
