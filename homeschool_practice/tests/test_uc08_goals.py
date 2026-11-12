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
from datetime import date, timedelta

from odoo import fields

from .common import PracticeCase

MONDAY = date(2026, 11, 16)


class TestGoals(PracticeCase):

    def setUp(self):
        super().setUp()
        self.Goal = self.env["homeschool.practice.goal"]
        self.Ach = self.env["homeschool.practice.goal.achievement"]

    def _quests_done_on(self, day, n):
        tmpl = self.env["homeschool.practice.quest.template"].search([], limit=n)
        for t in tmpl:
            self.Quest.create({"student_id": self.student.id, "template_id": t.id, "day": day, "done": True,
                               "progress": 1, "target": 1})

    def test_defaults(self):
        self.assertEqual(self.Goal._for(self.student, "day", MONDAY).target, 2)
        self.assertEqual(self.Goal._for(self.student, "week", MONDAY).target, 3)
        self.assertEqual(self.Goal._for(self.student, "month", MONDAY).target, 12)

    def test_day_week_no_streak(self):
        # Monday, Wednesday, Friday: not consecutive, still a week goal
        for k in (0, 2, 4):
            day = MONDAY + timedelta(days=k)
            self._quests_done_on(day, 2)
            new = self.student._practice_check_goals(day)
            self.assertIn("day", new.mapped("period"))
        week = self.Ach.search([("student_id", "=", self.student.id), ("period", "=", "week")])
        self.assertEqual(week.period_start, MONDAY)
        self.assertEqual(len(week), 1)
        # idempotent
        self.assertFalse(self.student._practice_check_goals(MONDAY + timedelta(days=4)))

    def test_one_quest_not_enough(self):
        self._quests_done_on(MONDAY, 1)
        self.assertFalse(self.student._practice_check_goals(MONDAY))

    def test_month(self):
        self.Goal._for(self.student, "month", MONDAY).target = 2
        for k in (0, 7):
            day = MONDAY + timedelta(days=k)
            self._quests_done_on(day, 2)
            self.student._practice_check_goals(day)
        month = self.Ach.search([("student_id", "=", self.student.id), ("period", "=", "month")])
        self.assertEqual(month.period_start, date(2026, 11, 1))

    def test_change_from_next_period(self):
        week_goal = self.Goal._for(self.student, "week", fields.Date.today())
        week_goal.action_change_target(5)
        self.assertEqual(self.Goal._for(self.student, "week", fields.Date.today()).target, 3)
        self.assertEqual(self.Goal._for(self.student, "week", fields.Date.today() + timedelta(days=7)).target, 5)

    def test_no_streak_anywhere(self):
        for model in ("homeschool.practice.goal", "homeschool.practice.goal.achievement", "homeschool.practice.quest",
                      "homeschool.student"):
            for name, f in self.env[model]._fields.items():
                self.assertNotIn("streak", name)
                self.assertNotIn("streak", (f.string or "").lower())
