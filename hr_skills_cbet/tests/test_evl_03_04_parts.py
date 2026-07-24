"""UC-EVL-03/04 — Conduct Part A & Part B.

EVL-03 AC1: opening snapshots the published criteria into result lines (frozen).
EVL-03 AC3: theoretical competencies produce no Part A lines.
EVL-04 AC1: question result lines snapshotted, essential flagged.
"""
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestEvlParts(CbetCommon):
    def test_snapshot_criteria_and_questions(self):
        comp = self._ready_competency(
            "EVL-03",
            crit_specs=[("security", "LOTO"), ("standard", "Rinse")],
            question_specs=[("Q1?", True), ("Q2?", False)])
        cand = self._make_employee("Cand 3")
        ev = self._make_evaluation(comp, cand)
        self.assertEqual(len(ev.criterion_result_ids), 2)
        self.assertEqual(len(ev.question_result_ids), 2)
        self.assertTrue(ev.competency_version_id)

    def test_snapshot_is_frozen(self):
        comp = self._ready_competency("EVL-04", crit_specs=[("standard", "Original")])
        cand = self._make_employee("Cand 4")
        ev = self._make_evaluation(comp, cand)
        # Change the catalog criterion after opening → result line stays frozen.
        comp.criterion_ids[0].text = "Changed in catalog"
        self.assertEqual(ev.criterion_result_ids[0].text, "Original")

    def test_theoretical_has_no_part_a(self):
        comp = self._ready_competency(
            "EVL-05", kind="theoretical", question_specs=[("Explain?", True)])
        cand = self._make_employee("Cand 5")
        ev = self._make_evaluation(comp, cand)
        self.assertEqual(len(ev.criterion_result_ids), 0)
        self.assertEqual(len(ev.question_result_ids), 1)
