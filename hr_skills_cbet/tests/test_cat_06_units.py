"""UC-CAT-06 — Evaluation units.

AC1: every competency has ≥1 unit (default unit auto-created).
AC2: units carry name, required flag (default true), own criterion lines,
     optional protocol overrides.
AC3: certification requires all required units passed (tested in EVL/STD).
"""
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatUnits(CbetCommon):
    def test_default_unit_present(self):
        c = self._make_competency("TST-60")
        self.assertEqual(len(c.unit_ids), 1)
        self.assertTrue(c.unit_ids.required)

    def test_multiple_units_with_own_criteria(self):
        c = self._make_competency("TST-61")
        annex = self.env["cbet.evaluation.unit"].create(
            {"competency_id": c.id, "name": "Annexe A — Fleck", "required": True})
        self.env["cbet.criterion"].create(
            {"unit_id": annex.id, "criterion_type": "standard", "text": "Set backwash"})
        self.assertEqual(len(c.unit_ids), 2)
        self.assertEqual(len(annex.criterion_ids), 1)
        self.assertIn(annex.criterion_ids, c.criterion_ids)
