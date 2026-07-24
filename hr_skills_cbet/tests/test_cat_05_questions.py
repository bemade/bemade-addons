"""UC-CAT-05 — Part B knowledge questions.

AC1: question has sequence, text, expected answer, section reference, essential flag.
AC2: questions belong to the competency (not per-unit) — one shared Part B bank.
"""
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatQuestions(CbetCommon):
    def test_question_on_competency_shared_bank(self):
        c = self._make_competency("TST-50")
        # Two units — the question bank is per competency, not per unit.
        self.env["cbet.evaluation.unit"].create(
            {"competency_id": c.id, "name": "Annexe B"})
        q = self.env["cbet.question"].create({
            "competency_id": c.id,
            "text": "What PPE is required?",
            "expected_answer": "Gloves, goggles",
            "section_ref": "§4",
            "essential": True,
        })
        self.assertIn(q, c.question_ids)
        self.assertTrue(q.essential)
