"""UC-STD-04 — Sub-qualifications.

AC1: a sub-qual is a standard flagged as an extension of a parent standard.
AC2: sub-qual state does not affect the parent qualification state.
"""
from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestStdSubQualification(CbetCommon):
    def test_sub_qualification_flag_and_independence(self):
        core = self._make_competency("STD-30")
        ext = self._make_competency("STD-31")
        parent = self._make_standard("Classe I", essentials=core)
        sub = self.env["cbet.standard"].create({
            "name": "Classe I-B",
            "parent_standard_id": parent.id,
            "line_ids": [(0, 0, {"competency_id": ext.id, "line_type": "essential"})],
        })
        self.assertTrue(sub.is_sub_qualification)
        self.assertFalse(parent.is_sub_qualification)

        emp = self._make_employee("Tech C")
        future = Date.today() + relativedelta(years=1)
        # Qualify the parent only.
        self._certify(emp, core, valid_to=future)
        pq = self.env["cbet.qualification"]._get_or_create(emp, parent)
        pq._recompute()
        sq = self.env["cbet.qualification"]._get_or_create(emp, sub)
        sq._recompute()
        self.assertEqual(pq.state, "qualified")
        self.assertEqual(sq.state, "in_progress")  # sub independent, not achieved
