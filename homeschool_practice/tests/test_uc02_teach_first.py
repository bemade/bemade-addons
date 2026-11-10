# -*- coding: utf-8 -*-
"""UC-02 — Teach first: a parent unlocks a unit; progression inside it is automatic.

Acceptance criteria
-------------------
1. ``homeschool.practice.unit.access`` (one per learner and unit): ``state``
   (``locked`` | ``unlocked``), ``unlocked_on``, ``unlocked_by``. Every unit starts
   locked; items of a locked unit are **never** scheduled.
2. **Unlocking is a parent decision, by unit** (a whole times table, a whole grammar
   concept): ``unit.action_unlock(student)``, idempotent (keeps the first date).
   Re-locking takes the unit out of scheduling and keeps its history.
3. **Progression inside an unlocked unit is automatic**: at unlock only the first
   ``step`` group is introduced (e.g. × 0 to × 5); the next item is introduced when
   the items already introduced are mostly secure (default: ≥ 80 % in box 3 or more).
   No parent action, no learner action.
4. The first time a unit is served, the payload carries its ``intro`` and
   ``first_time = True``; afterwards not.
5. A portal learner cannot unlock or lock anything (AccessError).
"""
from odoo.exceptions import AccessError

from .common import PracticeCase

class TestTeachFirst(PracticeCase):

    def test_locked_by_default_never_scheduled(self):
        session = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        self.assertFalse(session._current_item())
        self.assertFalse(self.Mastery.search([("student_id", "=", self.student.id)]))

    def test_unlock_by_unit_idempotent(self):
        self.t7.action_unlock(self.student)
        access = self.env["homeschool.practice.unit.access"].search(
            [("student_id", "=", self.student.id), ("unit_id", "=", self.t7.id)])
        self.assertEqual(access.state, "unlocked")
        first = access.unlocked_on
        self.assertEqual(access.unlocked_by, self.env.user)
        self.t7.action_unlock(self.student)
        self.assertEqual(access.unlocked_on, first)
        self.assertEqual(len(access), 1)

    def test_first_step_group_introduced(self):
        self.t7.action_unlock(self.student)
        rows = self.Mastery.search([("student_id", "=", self.student.id)])
        self.assertEqual(sorted(rows.item_id.mapped("step")), [0, 1, 2, 3, 4, 5])
        self.assertEqual(set(rows.mapped("state")), {"new"})
        self.assertEqual(rows.unit_id, self.t7)

    def test_automatic_progression(self):
        self.t7.action_unlock(self.student)
        rows = self.Mastery.search([("student_id", "=", self.student.id)])
        rows[:4].write({"box": 3})
        self.assertFalse(self.t7._progress(self.student))  # 4/6 < 80 %
        rows[:5].write({"box": 3})
        new = self.t7._progress(self.student)
        self.assertEqual(new.mapped("step"), [6])
        self.assertEqual(len(self.Mastery.search([("student_id", "=", self.student.id)])), 7)

    def test_relock_keeps_history(self):
        self.t7.action_unlock(self.student)
        self.run_session(unit=self.t7)
        attempts = self.Attempt.search_count([("student_id", "=", self.student.id)])
        self.t7.action_lock(self.student)
        session = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        self.assertFalse(session._current_item())
        self.assertEqual(self.Attempt.search_count([("student_id", "=", self.student.id)]), attempts)
        self.assertTrue(self.Mastery.search([("student_id", "=", self.student.id)]))

    def test_portal_cannot_unlock(self):
        user = self.portal_user()
        with self.assertRaises(AccessError):
            self.t7.with_user(user).action_unlock(self.student)
        manager = self.manager_user()
        self.t3.with_user(manager).action_unlock(self.student)
        self.assertTrue(self.t3._unlocked_for(self.student))

    def test_wizard_unlocks(self):
        w = self.env["homeschool.practice.unlock.wizard"].create({"student_id": self.student.id, "unit_ids": [(6, 0, (self.t7 | self.t3).ids)]})
        w.action_unlock()
        self.assertEqual(self.deck.unit_ids._unlocked_for(self.student), self.t7 | self.t3)
