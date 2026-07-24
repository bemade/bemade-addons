"""UC-CAT-07 — Evaluation protocol & validity policy.

AC1: defaults applied from company settings (default validity = 24 months),
     overridable per competency.
AC2: validity duration drives certification valid_to (tested in EVL-10).
Also seeds reprise deadline default (1 month) per UC-EVL-06 AC4.
"""
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestCatProtocolPolicy(CbetCommon):
    def test_validity_default_from_company(self):
        self.company.cbet_default_validity_months = 24
        c = self._make_competency("TST-70")
        self.assertEqual(c.validity_months, 24)

    def test_validity_overridable(self):
        c = self._make_competency("TST-71", validity_months=12)
        self.assertEqual(c.validity_months, 12)

    def test_reprise_deadline_default_one_month(self):
        self.company.cbet_reprise_deadline_days = 30
        c = self._make_competency("TST-72")
        self.assertEqual(c.reprise_deadline_days, 30)

    def test_designated_trainers_settable(self):
        c = self._make_competency("TST-73")
        c.designated_trainer_ids = self.manager
        self.assertIn(self.manager, c.designated_trainer_ids)
