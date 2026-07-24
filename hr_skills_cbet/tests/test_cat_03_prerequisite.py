"""UC-CAT-03 — Typed prerequisite graph.

AC1: edges carry a type (obligatoire/recommandé).
AC2: cycle creation blocked (direct + transitive).
AC3: self-prerequisite blocked.
AC4: transitive obligatory closure helper.
"""
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatPrerequisite(CbetCommon):
    def setUp(self):
        super().setUp()
        self.a = self._make_competency("TST-01")
        self.b = self._make_competency("TST-02")
        self.c = self._make_competency("TST-03")

    def _edge(self, comp, prereq, kind="obligatoire"):
        return self.env["cbet.prerequisite"].create({
            "competency_id": comp.id,
            "prerequisite_id": prereq.id,
            "prereq_type": kind,
        })

    def test_self_prerequisite_blocked(self):
        with self.assertRaises(ValidationError):
            self._edge(self.a, self.a)

    def test_direct_cycle_blocked(self):
        self._edge(self.a, self.b)
        with self.assertRaises(ValidationError):
            self._edge(self.b, self.a)

    def test_transitive_cycle_blocked(self):
        self._edge(self.a, self.b)
        self._edge(self.b, self.c)
        with self.assertRaises(ValidationError):
            self._edge(self.c, self.a)

    def test_obligatory_closure(self):
        self._edge(self.a, self.b, "obligatoire")
        self._edge(self.b, self.c, "obligatoire")
        closure = self.a._obligatory_closure()
        self.assertEqual(closure, self.a | self.b | self.c)

    def test_recommended_excluded_from_closure(self):
        self._edge(self.a, self.b, "recommande")
        closure = self.a._obligatory_closure()
        self.assertEqual(closure, self.a)
