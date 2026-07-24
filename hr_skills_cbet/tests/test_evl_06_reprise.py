"""UC-EVL-06 — Reprise ciblée follow-up.

AC1: a reprise contains only the failed 🔒/⚠️ items (criteria + essential Qs).
AC3: reprise cannot spawn a reprise (single retry); deadline set (AC4).
"""
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestEvlReprise(CbetCommon):
    def _failed_eval(self):
        comp = self._ready_competency(
            "EVL-07",
            crit_specs=[("security", "LOTO"), ("critical", "Torque"),
                        ("standard", "Tidy")],
            question_specs=[("Essential Q?", True), ("Nice Q?", False)])
        comp.reprise_deadline_days = 30
        cand = self._make_employee("Cand 7")
        ev = self._make_evaluation(comp, cand)
        self._set_results(ev, crit="reussi", question="acquis")
        # Fail one critical criterion and the essential question.
        ev.criterion_result_ids.filtered(
            lambda c: c.criterion_type == "critical").result = "echec"
        ev.question_result_ids.filtered("essential").result = "a_revoir"
        return ev

    def test_reprise_contains_only_failed_items(self):
        ev = self._failed_eval()
        self._sign_and_complete(ev, decision="reprise_ciblee")
        reprise = ev.reprise_child_ids
        self.assertEqual(len(reprise), 1)
        # Only the failed critical criterion, not the passed security/standard.
        self.assertEqual(len(reprise.criterion_result_ids), 1)
        self.assertEqual(reprise.criterion_result_ids.criterion_type, "critical")
        # Only the failed essential question.
        self.assertEqual(len(reprise.question_result_ids), 1)
        self.assertTrue(reprise.question_result_ids.essential)
        self.assertTrue(reprise.reprise_deadline)
        self.assertTrue(reprise.is_reprise)

    def test_reprise_cannot_spawn_reprise(self):
        ev = self._failed_eval()
        self._sign_and_complete(ev, decision="reprise_ciblee")
        reprise = ev.reprise_child_ids
        # A reprise that itself fails cannot spawn another reprise.
        with self.assertRaises(UserError):
            reprise._create_reprise()
