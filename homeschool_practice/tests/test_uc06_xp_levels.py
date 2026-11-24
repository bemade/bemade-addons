# -*- coding: utf-8 -*-
"""UC-06 — XP and levels (effort and progress, never speed).

Acceptance criteria
-------------------
1. ``homeschool.practice.xp`` is an append-only ledger: ``student_id``, ``amount``,
   ``reason`` (``answer`` | ``correct`` | ``session_done`` | ``automatic`` | ``quest``),
   ``source`` (reference to the attempt / session / mastery / quest), ``date``.
   No write, no unlink except by a system user.
2. Defaults (configurable per family): +1 per answer (a miss earns it too), +1 more if
   correct, +5 per finished session, +10 when an item becomes ``automatic``, +quest XP.
3. **No XP rule reads a latency.** Two identical sessions answered fast and slow earn
   the same XP.
4. ``student.practice_xp`` and ``student.practice_level`` are computed from the ledger;
   level *n* needs ``50 × (n − 1) × n / 2`` XP in total by default (level 1 at 0, then
   50, 150, 300…).
   Changing the curve recomputes levels without touching the ledger.
5. A level-up is reported once in the answer payload (``level_up: {from, to}``).
6. XP never creates a reward (rewards come from goals, UC-09).
"""
from odoo.exceptions import AccessError, UserError

from .common import PracticeCase

class TestXpLevels(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t7.action_unlock(self.student)

    def test_xp_per_answer_and_session(self):
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        item = s._current_item()
        _a, ev = s._answer(item, item.answer)
        self.assertEqual(ev["xp"], 2)
        item = s._current_item()
        _a, ev = s._answer(item, "999")
        self.assertEqual(ev["xp"], 1)  # a miss earns the effort XP
        self.answer_all(s)
        ev = s._finish()
        self.assertEqual(ev["xp"], 5)
        reasons = self.Xp.search([("student_id", "=", self.student.id)]).mapped("reason")
        self.assertIn("session_done", reasons)

    def test_no_xp_rule_reads_latency(self):
        fast = self.run_session(unit=self.t7, first_touch=300)
        xp_fast = sum(self.Xp.search([("student_id", "=", self.student.id)]).mapped("amount"))
        self.Xp.search([]).sudo().unlink()
        self.Mastery.search([]).unlink()
        self.t7._introduce(self.student, 6)
        slow = self.run_session(unit=self.t7, first_touch=9000)
        xp_slow = sum(self.Xp.search([("student_id", "=", self.student.id)]).mapped("amount"))
        self.assertEqual(xp_fast, xp_slow)

    def test_level_curve(self):
        s = self.student
        self.assertEqual(s.practice_level, 1)
        self.assertEqual([s._practice_level_req(n) for n in (1, 2, 3, 4)], [0, 50, 150, 300])
        self.Xp._award(s, 149, "adjustment")
        s.invalidate_recordset()
        self.assertEqual((s.practice_xp, s.practice_level), (149, 2))
        self.company.practice_level_base = 10
        s.invalidate_recordset()
        self.assertEqual(s.practice_level, 5)  # 100 for level 5, 150 for level 6
        self.assertEqual(self.Xp.search_count([("student_id", "=", s.id)]), 1)

    def test_level_up_reported(self):
        self.Xp._award(self.student, 49, "adjustment")
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        item = s._current_item()
        _a, ev = s._answer(item, item.answer)
        self.assertEqual(ev["level_up"], {"from": 1, "to": 2})

    def test_append_only(self):
        line = self.Xp._award(self.student, 5, "adjustment")
        manager = self.manager_user()
        with self.assertRaises(UserError):
            line.with_user(manager).write({"amount": 50})
        with self.assertRaises(UserError):
            line.with_user(manager).unlink()

    def test_xp_never_rewards(self):
        rt = self.env["homeschool.reward.type"].create({"name": "Gaming time", "unit": "min"})
        self.Xp._award(self.student, 5000, "adjustment")
        self.assertFalse(self.env["homeschool.reward.ledger"].search([("student_id", "=", self.student.id)]))
