# -*- coding: utf-8 -*-
"""UC-10 — Access: learners, educators, families.

Acceptance criteria
-------------------
1. A **portal learner** reaches his own practice only through the portal API (UC-11):
   decks, his quests, goals, XP, level, badges and reward balances. Direct ORM reads of
   sessions, attempts and mastery as the learner → AccessError; another learner's data
   → AccessError; no unlink anywhere.
2. **Resource users** (the outside teacher, attached to the student) read all practice
   data of their students, timing and mastery included, and write nothing. Reward
   ledgers: not visible to them.
3. **Managers** see and manage the records of their companies only.
4. Reward ledger lines are created by the system (goals) or by managers (redemptions,
   adjustments); a learner or a resource user cannot create or alter them.
"""
from odoo.exceptions import AccessError, UserError

from .common import PracticeCase

class TestAccess(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t7.action_unlock(self.student)
        self.learner = self.portal_user()
        self.student.user_id = self.learner
        self.teacher = self.resource_user(self.student)
        self.session = self.run_session(unit=self.t7)
        self.gaming = self.env["homeschool.reward.type"].create({"name": "Gaming time", "unit": "min"})
        self.env["homeschool.reward.ledger"].create({"student_id": self.student.id, "reward_type_id": self.gaming.id,
                                                     "kind": "adjustment", "amount": 10})

    def test_learner_reads_progress_not_verdicts(self):
        L = self.learner
        self.assertTrue(self.Xp.with_user(L).search([]))
        self.assertTrue(self.env["homeschool.reward.balance"].with_user(L).search([]))
        self.assertTrue(self.env["homeschool.reward.ledger"].with_user(L).search([]))
        for model in ("homeschool.practice.session", "homeschool.practice.attempt", "homeschool.practice.mastery",
                      "homeschool.practice.mastery.history", "homeschool.practice.unit.access"):
            self.assertFalse(self.env[model].with_user(L).search([]), model)
        with self.assertRaises(AccessError):
            self.session.with_user(L).read(["item_count"])

    def test_learner_writes_nothing(self):
        L = self.learner
        with self.assertRaises(AccessError):
            self.env["homeschool.reward.ledger"].with_user(L).create(
                {"student_id": self.student.id, "reward_type_id": self.gaming.id, "kind": "adjustment", "amount": 100})
        with self.assertRaises(AccessError):
            self.Session.with_user(L).create({"student_id": self.student.id, "deck_id": self.deck.id})
        with self.assertRaises(UserError):
            self.Xp.with_user(L).search([], limit=1).unlink()

    def test_other_learner(self):
        other = self.portal_user(partner=self.partner_b, login="other")
        self.student_b.user_id = other
        self.assertFalse(self.Xp.with_user(other).search([]))
        self.assertFalse(self.env["homeschool.reward.ledger"].with_user(other).search([]))

    def test_educator_reads_all_but_rewards(self):
        T = self.teacher
        self.assertTrue(self.Attempt.with_user(T).search([]))
        self.assertTrue(self.Attempt.with_user(T).search([], limit=1).first_touch_ms)
        self.assertTrue(self.Mastery.with_user(T).search([]))
        self.assertTrue(self.Session.with_user(T).search([]))
        self.assertFalse(self.env["homeschool.reward.ledger"].with_user(T).search([]))
        self.assertFalse(self.env["homeschool.reward.balance"].with_user(T).search([]))
        with self.assertRaises(AccessError):
            self.Mastery.with_user(T).search([], limit=1).write({"box": 5})

    def test_managers_by_company(self):
        mgr = self.manager_user()
        mgr_b = self.manager_user(self.company_b, login="mgr_b")
        self.assertTrue(self.Attempt.with_user(mgr).search([]))
        self.assertFalse(self.Attempt.with_user(mgr_b).search([]))
        self.assertFalse(self.Mastery.with_user(mgr_b).search([]))
        self.assertFalse(self.Deck.with_user(mgr_b).search([]))
