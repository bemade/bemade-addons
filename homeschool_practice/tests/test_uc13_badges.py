# -*- coding: utf-8 -*-
"""UC-13 — Badges: celebrating accomplishments.

Acceptance criteria
-------------------
1. ``homeschool.practice.badge.template``: ``name`` and ``description`` (translatable),
   ``icon``, ``kind``, ``threshold``, ``deck_id`` / ``unit_id`` when it targets one,
   ``repeatable``, ``company_id``, ``active``. Kinds:
   ``xp_total`` (reach N XP), ``xp_day`` (N XP in one day), ``perfect_session`` (a
   session without a miss; N of them), ``sessions_total`` (N sessions),
   ``goals_total`` (N daily goals reached), ``unit_proficiency`` (a unit reaches a
   proficiency level: share of its items secure — bronze / silver / gold thresholds),
   ``level`` (reach level N).
2. ``homeschool.practice.badge``: one per learner and template (unique unless
   ``repeatable``), ``earned_at``, ``seen`` (flagged new in the API until shown).
3. Badges are evaluated after each answer and each finished session; an earned badge
   is never taken back (a unit sliding back does not remove its badge).
4. **No badge depends on the time of day or on speed** (no kind reads a clock hour or a
   latency).
5. ``unit_proficiency`` names a level for the unit as a whole; it never reveals which
   items are secure.
6. Badges carry no reward (rewards come from goals, UC-09).
"""
from .common import PracticeCase

class TestBadges(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t7.action_unlock(self.student)
        self.Badge = self.env["homeschool.practice.badge"]
        self.BT = self.env["homeschool.practice.badge.template"]

    def earned(self, xmlid):
        return self.Badge.search([("student_id", "=", self.student.id),
                                  ("template_id", "=", self.env.ref("homeschool_practice." + xmlid).id)])

    def test_xp_badges_once(self):
        self.Xp._award(self.student, 120, "adjustment")
        self.run_session(unit=self.t7)
        self.assertEqual(len(self.earned("badge_xp_100")), 1)
        self.assertTrue(self.earned("badge_xp_day_50"))
        self.run_session(unit=self.t7)
        self.assertEqual(len(self.earned("badge_xp_100")), 1)

    def test_perfect_and_sessions(self):
        s = self.run_session(unit=self.t7)
        self.assertTrue(s.perfect)
        self.assertTrue(self.earned("badge_perfect_1"))
        rep = self.BT.create({"name": "Perfect again", "kind": "perfect_session", "threshold": 1, "repeatable": True})
        self.run_session(unit=self.t7)
        self.run_session(unit=self.t7)
        self.assertEqual(self.Badge.search_count([("student_id", "=", self.student.id), ("template_id", "=", rep.id)]), 2)

    def test_unit_proficiency_never_taken_back(self):
        items = self.t7.item_ids
        self.t7._introduce(self.student, 20)
        self.Mastery.search([("student_id", "=", self.student.id)])[:7].write({"box": 3})
        self.student._practice_check_badges()
        bronze = self.earned("badge_unit_bronze")
        self.assertEqual(bronze.unit_id, self.t7)
        self.assertFalse(self.earned("badge_unit_silver"))
        self.Mastery.search([("student_id", "=", self.student.id)]).write({"box": 1})
        self.student._practice_check_badges()
        self.assertTrue(bronze.exists())

    def test_no_badge_reads_clock_or_speed(self):
        kinds = dict(self.BT._fields["kind"].selection)
        for k in kinds:
            self.assertNotIn("dawn", k)
            self.assertNotIn("hour", k)
            self.assertNotIn("speed", k)
            self.assertNotIn("fast", k)

    def test_badges_carry_no_reward(self):
        self.env["homeschool.reward.type"].create({"name": "Gaming time", "unit": "min"})
        self.Xp._award(self.student, 6000, "adjustment")
        self.student._practice_check_badges()
        self.assertTrue(self.earned("badge_xp_5000"))
        self.assertFalse(self.env["homeschool.reward.ledger"].search([("student_id", "=", self.student.id)]))
