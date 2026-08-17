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

    def test_grid_comes_from_the_pinned_version_not_the_live_catalog(self):
        # EVL-03 AC1 — the evaluation pins a published version, so its grid must
        # be built from that version's snapshot. Live catalogue rows can have
        # moved on (a re-import replaces them wholesale) and an evaluation
        # stamped v1.0 must never contain criteria that v1.0 never had.
        comp = self._ready_competency("EVL-11", crit_specs=[("security", "As published")],
                                      question_specs=[("Published question?", True)])
        # The catalogue moves on: criteria and questions replaced, as a
        # re-import would do. The competency is still sitting at v1.0.
        comp.criterion_ids.unlink()
        comp.question_ids.unlink()
        self._add_criteria(comp, [("standard", "Added after publication")])
        self.env["cbet.question"].create({
            "competency_id": comp.id, "text": "Added after publication?",
            "essential": False})

        ev = self._make_evaluation(comp, self._make_employee("Cand 11"))
        self.assertEqual(ev.criterion_result_ids.mapped("text"), ["As published"])
        self.assertEqual(ev.criterion_result_ids.criterion_type, "security")
        self.assertEqual(ev.question_result_ids.mapped("text"), ["Published question?"])
        self.assertTrue(ev.question_result_ids.essential)
        # The source links are dropped rather than pointed at deleted rows.
        self.assertFalse(ev.criterion_result_ids.source_criterion_id)

    def test_theoretical_has_no_part_a(self):
        comp = self._ready_competency(
            "EVL-05", kind="theoretical", question_specs=[("Explain?", True)])
        cand = self._make_employee("Cand 5")
        ev = self._make_evaluation(comp, cand)
        self.assertEqual(len(ev.criterion_result_ids), 0)
        self.assertEqual(len(ev.question_result_ids), 1)
