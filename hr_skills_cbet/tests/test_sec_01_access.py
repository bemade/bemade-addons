"""UC-SEC-01 — Role access matrix (record rules).

AC2: candidate reads own records only, not other employees'.
AC4: evaluator sees evaluations only when assigned to conduct them.
AC5: manager full visibility.
"""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestSecAccess(CbetCommon):
    def setUp(self):
        super().setUp()
        self.comp = self._ready_competency("SEC-01", crit_specs=[("standard", "Do")])
        # Candidate user linked to an employee.
        self.cand_user = self.env["res.users"].create({
            "name": "Cand User", "login": "cand_user", "email": "cu@example.com",
            "group_ids": [Command.link(self.env.ref("hr_skills_cbet.group_cbet_user").id)],
        })
        self.cand_emp = self.env["hr.employee"].create(
            {"name": "Cand S", "user_id": self.cand_user.id})
        self.other_emp = self._make_employee("Other S")

    def test_candidate_reads_own_certification_only(self):
        own = self._certify(self.cand_emp, self.comp)
        other = self._certify(self.other_emp, self.comp)
        visible = self.env["cbet.certification"].with_user(self.cand_user).search([])
        self.assertIn(own, visible)
        self.assertNotIn(other, visible)

    def test_evaluator_sees_assigned_evaluations_only(self):
        second_eval = self.env["res.users"].create({
            "name": "Eval2", "login": "eval2", "email": "e2@example.com",
            "group_ids": [Command.link(self.env.ref("hr_skills_cbet.group_cbet_evaluator").id)],
        })
        self.comp.designated_trainer_ids = self.evaluator + second_eval
        mine = self._make_evaluation(self.comp, self.other_emp, evaluator=self.evaluator)
        theirs = self._make_evaluation(self.comp, self.other_emp, evaluator=second_eval)
        visible = self.env["cbet.evaluation"].with_user(self.evaluator).search([])
        self.assertIn(mine, visible)
        self.assertNotIn(theirs, visible)

    def test_manager_sees_all(self):
        e = self._make_evaluation(self.comp, self.other_emp, evaluator=self.evaluator)
        self.assertIn(e, self.env["cbet.evaluation"].with_user(self.manager).search([]))
