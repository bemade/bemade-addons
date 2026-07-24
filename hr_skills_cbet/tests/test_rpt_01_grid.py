"""UC-RPT-01 — Evaluation grid report.

AC1: QWeb renders header, Part A, Part B, decision, signatures.
AC2: renders blank (pre-evaluation) and completed variants.
"""
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestRptGrid(CbetCommon):
    def test_render_completed_grid(self):
        comp = self._ready_competency(
            "RPT-01", crit_specs=[("security", "LOTO")],
            question_specs=[("Q?", True)])
        cand = self._make_employee("Cand R1")
        ev = self._make_evaluation(comp, cand)
        self._set_results(ev, crit="reussi", question="acquis")
        self._sign_and_complete(ev, decision="reussi")

        html, _type = self.env["ir.actions.report"]._render_qweb_html(
            "hr_skills_cbet.report_cbet_evaluation", ev.ids)
        self.assertIn(b"RPT-01", html)
        self.assertIn(b"Part A", html)
        self.assertIn(b"Part B", html)

    def test_render_blank_worksheet(self):
        comp = self._ready_competency("RPT-02", crit_specs=[("standard", "Do")])
        cand = self._make_employee("Cand R2")
        ev = self._make_evaluation(comp, cand)  # not completed → blank worksheet
        html, _type = self.env["ir.actions.report"]._render_qweb_html(
            "hr_skills_cbet.report_cbet_evaluation", ev.ids)
        self.assertIn(b"RPT-02", html)
