"""UC-EVL-05 — Decision computation.

AC1: indicators — all security+critical réussi (s.o. excluded); ratio of réussi
     over ALL applicable criteria ≥ threshold; essential questions acquis.
AC3: cannot record réussi when a security/critical criterion is échec.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestEvlDecision(CbetCommon):
    def _eval(self):
        comp = self._ready_competency(
            "EVL-06",
            crit_specs=[("security", "LOTO"), ("standard", "S1"),
                        ("standard", "S2"), ("standard", "S3"),
                        ("standard", "S4")],
            question_specs=[("Q?", True)])
        comp.pass_threshold = 80.0
        cand = self._make_employee("Cand 6")
        return self._make_evaluation(comp, cand)

    def test_all_pass_is_reussi(self):
        ev = self._eval()
        self._set_results(ev, crit="reussi", question="acquis")
        self.assertTrue(ev.security_critical_ok)
        self.assertTrue(ev.computed_pass)
        self.assertEqual(ev.suggested_decision, "reussi")

    def test_ratio_over_all_applicable(self):
        ev = self._eval()
        self._set_results(ev, crit="reussi", question="acquis")
        # Fail 1 of 5 criteria (a standard one) → 4/5 = 80% ≥ threshold → pass.
        std_lines = ev.criterion_result_ids.filtered(
            lambda c: c.criterion_type == "standard")
        std_lines[0].result = "echec"
        self.assertEqual(ev.overall_ratio, 80.0)
        self.assertTrue(ev.computed_pass)
        # Fail a second → 3/5 = 60% < 80% → fail.
        std_lines[1].result = "echec"
        self.assertEqual(ev.overall_ratio, 60.0)
        self.assertFalse(ev.computed_pass)

    def test_security_hard_gate(self):
        ev = self._eval()
        self._set_results(ev, crit="reussi", question="acquis")
        sec = ev.criterion_result_ids.filtered(
            lambda c: c.criterion_type == "security")
        sec.result = "echec"
        self.assertFalse(ev.security_critical_ok)
        self.assertFalse(ev.computed_pass)
        # AC3 — cannot record réussi with a security échec.
        with self.assertRaises(ValidationError):
            ev.decision = "reussi"

    def test_essential_question_gate(self):
        ev = self._eval()
        self._set_results(ev, crit="reussi", question="acquis")
        ev.question_result_ids.filtered("essential").result = "a_revoir"
        self.assertFalse(ev.essential_questions_ok)
        self.assertFalse(ev.computed_pass)
