"""UC-EVL-01 — Evaluation session.

AC1: session groups evaluation records; each targets one competency unit.
AC2: creating an evaluation from a session pre-fills evaluator, date, place.
"""
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestEvlSession(CbetCommon):
    def test_session_groups_evaluations(self):
        comp = self._ready_competency("EVL-01")
        cand = self._make_employee("Cand 1")
        session = self.env["cbet.evaluation.session"].create({
            "name": "S1", "candidate_id": cand.id, "evaluator_id": self.evaluator.id,
        })
        ev = self.env["cbet.evaluation"].create({
            "session_id": session.id,
            "competency_id": comp.id,
            "unit_id": comp.unit_ids[:1].id,
            "candidate_id": cand.id,
            "evaluator_id": self.evaluator.id,
        })
        self.assertEqual(session.evaluation_count, 1)
        self.assertIn(ev, session.evaluation_ids)
