"""UC-CAT-04 — Performance criteria.

AC1: criterion has sequence, type ∈ {security, critical, standard}, text,
     verification method, tolerance; belongs to an evaluation unit.
AC2: overall pass threshold configurable per competency (default 80 %).
AC3: criteria orderable and copyable when duplicating a competency.
"""
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatCriteria(CbetCommon):
    def test_criterion_belongs_to_unit_and_competency(self):
        c = self._make_competency("TST-40")
        crit = self._add_criteria(c, [("security", "Lockout/tagout applied")])
        self.assertEqual(crit.competency_id, c)
        self.assertEqual(crit.unit_id, c.unit_ids[:1])

    def test_default_threshold(self):
        c = self._make_competency("TST-41")
        self.assertEqual(c.pass_threshold, 80.0)

    def test_criteria_copied_on_duplicate(self):
        c = self._make_competency("TST-42")
        self._add_criteria(c, [("standard", "Step 1"), ("critical", "Step 2")])
        copy = c.copy({"code": "TST-43"})
        self.assertEqual(len(copy.criterion_ids), 2)
        # Copy is independent.
        self.assertNotEqual(copy.criterion_ids, c.criterion_ids)
