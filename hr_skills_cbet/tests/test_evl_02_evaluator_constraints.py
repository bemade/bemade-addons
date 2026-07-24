"""UC-EVL-02 — Evaluator constraints.

AC1: evaluator must be a designated trainer for that competency.
AC2: evaluator ≠ candidate; evaluator ≠ candidate's direct trainer (override + log).
"""
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestEvlEvaluatorConstraints(CbetCommon):
    def setUp(self):
        super().setUp()
        self.comp = self._ready_competency("EVL-02")
        self.cand = self._make_employee("Cand 2")

    def _new(self, evaluator):
        return self.env["cbet.evaluation"].create({
            "competency_id": self.comp.id,
            "unit_id": self.comp.unit_ids[:1].id,
            "candidate_id": self.cand.id,
            "evaluator_id": evaluator.id,
        })

    def test_non_designated_trainer_blocked(self):
        other = self.env["res.users"].create({
            "name": "Other", "login": "other_eval", "email": "o@example.com",
            "group_ids": [Command.link(self.env.ref("hr_skills_cbet.group_cbet_evaluator").id)],
        })
        with self.assertRaises(ValidationError):
            self._new(other)

    def test_evaluator_is_candidate_blocked(self):
        self.cand.user_id = self.evaluator
        with self.assertRaises(ValidationError):
            self._new(self.evaluator)

    def test_evaluator_is_direct_trainer_blocked(self):
        self.env["cbet.training.line"].create({
            "employee_id": self.cand.id, "competency_id": self.comp.id,
            "trainer_id": self.evaluator.id,
        })
        with self.assertRaises(ValidationError):
            self._new(self.evaluator)

    def test_manager_override_context(self):
        self.env["cbet.training.line"].create({
            "employee_id": self.cand.id, "competency_id": self.comp.id,
            "trainer_id": self.evaluator.id,
        })
        # Override bypasses the independence constraint.
        ev = self.env["cbet.evaluation"].with_context(
            cbet_override_independence=True).create({
                "competency_id": self.comp.id,
                "unit_id": self.comp.unit_ids[:1].id,
                "candidate_id": self.cand.id,
                "evaluator_id": self.evaluator.id,
            })
        self.assertTrue(ev)
