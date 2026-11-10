# -*- coding: utf-8 -*-
"""UC-09 — Family-defined rewards: earned by goals, never expire.

Acceptance criteria
-------------------
1. ``homeschool.reward.type``: ``name`` (e.g. « Temps de jeu »), ``unit`` (e.g.
   « min », « $ »), ``company_id``, ``active``. Families create their own; the module
   ships none active by default.
2. ``homeschool.reward.rule``: ``student_id``, ``goal_period`` (day / week / month),
   ``reward_type_id``, ``amount`` (> 0), ``date_from``. Several rules may pay for one
   goal (e.g. a week pays minutes AND credit). A new rule from a date replaces the
   previous one for later achievements only.
3. ``homeschool.reward.ledger``: append-only; ``student_id``, ``reward_type_id``,
   ``kind`` (``earned`` | ``redeemed`` | ``adjustment``), ``amount`` (signed),
   ``date``, ``source`` (the goal achievement, or the redemption), ``note``,
   ``recorded_by``. A goal achievement writes one ``earned`` line per applicable rule,
   **with the amount of the rule in force at that moment**, once (idempotent).
4. **No expiry:** there is no expiry field or cron; a balance earned months ago is
   still whole.
5. ``student.reward_balance_ids`` (per type) = sum of the ledger. A redemption is
   recorded by a manager (``action_redeem(type, amount, note)``) and cannot take a
   balance below zero (UserError).
6. XP never appears in the ledger, and no ledger line is created from XP.
7. Rewards of one family are never visible to another (company rules).
"""
from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError

from .common import PracticeCase

MONDAY = date(2026, 11, 16)


class TestRewards(PracticeCase):

    def setUp(self):
        super().setUp()
        self.RType = self.env["homeschool.reward.type"]
        self.Rule = self.env["homeschool.reward.rule"]
        self.Ledger = self.env["homeschool.reward.ledger"]
        self.gaming = self.RType.create({"name": "Gaming time", "unit": "min"})
        self.credit = self.RType.create({"name": "Credit", "unit": "$"})
        self.Rule.create({"student_id": self.student.id, "goal_period": "day", "reward_type_id": self.gaming.id,
                          "amount": 15, "date_from": "2026-01-01"})
        self.Rule.create({"student_id": self.student.id, "goal_period": "week", "reward_type_id": self.gaming.id,
                          "amount": 30, "date_from": "2026-01-01"})
        self.Rule.create({"student_id": self.student.id, "goal_period": "week", "reward_type_id": self.credit.id,
                          "amount": 2, "date_from": "2026-01-01"})

    def _reach_day(self, day):
        tmpl = self.env["homeschool.practice.quest.template"].search([], limit=2)
        for t in tmpl:
            self.Quest.create({"student_id": self.student.id, "template_id": t.id, "day": day, "done": True,
                               "progress": 1, "target": 1})
        new = self.student._practice_check_goals(day)
        for ach in new:
            self.student._practice_earn(ach)
        return new

    def test_none_shipped(self):
        self.assertFalse(self.RType.search([("id", "not in", (self.gaming | self.credit).ids)]))

    def test_goal_earns_once_with_rule_in_force(self):
        new = self._reach_day(MONDAY)
        self.assertEqual(self.student._reward_balance(self.gaming), 15)
        self.student._practice_earn(new)  # idempotent
        self.assertEqual(self.student._reward_balance(self.gaming), 15)
        # the rate changes from Wednesday: Monday's line keeps its amount
        self.Rule.create({"student_id": self.student.id, "goal_period": "day", "reward_type_id": self.gaming.id,
                          "amount": 20, "date_from": MONDAY + timedelta(days=2)})
        self._reach_day(MONDAY + timedelta(days=1))
        self._reach_day(MONDAY + timedelta(days=2))
        lines = self.Ledger.search([("student_id", "=", self.student.id), ("kind", "=", "earned")], order="id")
        # 3 days (15 + 15 + 20) + the week (30 min and 2 $)
        self.assertEqual(self.student._reward_balance(self.gaming), 80)
        self.assertEqual(self.student._reward_balance(self.credit), 2)
        self.assertEqual(lines.filtered(lambda l: l.reward_type_id == self.gaming)[0].amount, 15)

    def test_redeem_never_below_zero_no_expiry(self):
        self._reach_day(MONDAY)
        old = self.Ledger.search([("student_id", "=", self.student.id)])
        self.assertNotIn("expir", " ".join(self.Ledger._fields))
        manager = self.manager_user()
        self.student.with_user(manager).action_reward_redeem(self.gaming, 10, "Minecraft")
        self.assertEqual(self.student._reward_balance(self.gaming), 5)
        with self.assertRaises(UserError):
            self.student.with_user(manager).action_reward_redeem(self.gaming, 6)
        learner = self.portal_user()
        self.student.user_id = learner
        with self.assertRaises(AccessError):
            self.student.with_user(learner).action_reward_redeem(self.gaming, 1)
        bal = self.env["homeschool.reward.balance"].search([("student_id", "=", self.student.id), ("reward_type_id", "=", self.gaming.id)])
        self.assertEqual(bal.balance, 5)

    def test_redeem_wizard(self):
        self._reach_day(MONDAY)
        w = self.env["homeschool.reward.redeem.wizard"].create(
            {"student_id": self.student.id, "reward_type_id": self.gaming.id, "amount": 5})
        self.assertEqual(w.balance, 15)
        w.action_redeem()
        self.assertEqual(self.student._reward_balance(self.gaming), 10)

    def test_ledger_append_only(self):
        self._reach_day(MONDAY)
        line = self.Ledger.search([("student_id", "=", self.student.id)], limit=1)
        with self.assertRaises(UserError):
            line.with_user(self.manager_user()).write({"amount": 99})

    def test_families_separate(self):
        self._reach_day(MONDAY)
        manager_b = self.manager_user(self.company_b, login="mgr_b")
        self.assertFalse(self.Ledger.with_user(manager_b).search([]))
        self.assertFalse(self.RType.with_user(manager_b).search([]))

    def test_session_flow_pays(self):
        self.t7.action_unlock(self.student)
        Template = self.env["homeschool.practice.quest.template"]
        Template.search([]).write({"active": False})
        Template.create({"name": "Answer {target}", "kind": "answers", "target": 1})
        Template.create({"name": "{target} right", "kind": "no_hint", "target": 1})
        self.student.practice_weekdays = "1234567"
        self.Quest._draw(self.student)
        s = self.Session._start(self.student, self.deck, kind="unit", unit=self.t7)
        item = s._current_item()
        _a, ev = s._answer(item, item.answer)
        self.assertEqual(len(ev["quests_done"]), 2)
        self.assertIn("day", ev["goals_reached"])
        self.assertEqual(ev["rewards"][0]["amount"], 15)
