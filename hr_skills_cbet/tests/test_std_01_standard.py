"""UC-STD-01 — Define qualification standard.

AC1: standard has name, role description, essential + optional lines.
AC2: full requirement set = transitive closure of obligatory prerequisites.
AC3: closure distinguishes essential vs pulled-in-by-prerequisite.
"""
from odoo import Command
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestStdStandard(CbetCommon):
    def test_closure_over_obligatory_prerequisites(self):
        a = self._make_competency("STD-01")
        b = self._make_competency("STD-02")
        c = self._make_competency("STD-03")
        # a requires b (obligatoire) and c (recommandé).
        self.env["cbet.prerequisite"].create([
            {"competency_id": a.id, "prerequisite_id": b.id, "prereq_type": "obligatoire"},
            {"competency_id": a.id, "prerequisite_id": c.id, "prereq_type": "recommande"},
        ])
        std = self._make_standard("Classe I", essentials=a)

        self.assertEqual(std.essential_competency_ids, a)
        self.assertEqual(std.closed_competency_ids, a | b)  # c excluded (recommandé)
        self.assertEqual(std.pulled_in_competency_ids, b)
        self.assertEqual(std.required_count, 2)
