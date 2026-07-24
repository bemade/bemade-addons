"""UC-STD-03 — hr.skill tie-back grant.

AC1: on qualification achieved, a dated hr.employee.skill row is created
     (valid_from = achievement date; valid_to = rolling min of the whole closed
     set's expiries).
AC2: on suspension/lapse the row is closed; on restoration a new row opens.
AC3: no per-competency rows pollute hr.employee.skill.
"""
from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestStdTieback(CbetCommon):
    def setUp(self):
        super().setUp()
        self.a = self._make_competency("STD-20")
        self.b = self._make_competency("STD-21")
        self.env["cbet.prerequisite"].create(
            {"competency_id": self.a.id, "prerequisite_id": self.b.id,
             "prereq_type": "obligatoire"})
        self.skill = self._make_cert_skill("Tech Classe I")
        self.std = self._make_standard("Classe I", essentials=self.a, skill=self.skill)
        self.emp = self._make_employee("Tech B")
        self.qual = self.env["cbet.qualification"]._get_or_create(self.emp, self.std)
        self.exp_a = Date.today() + relativedelta(years=2)
        self.exp_b = Date.today() + relativedelta(years=1)

    def test_tieback_created_with_rolling_min_valid_to(self):
        self._certify(self.emp, self.a, valid_to=self.exp_a)
        self._certify(self.emp, self.b, valid_to=self.exp_b)
        self.qual._recompute()
        row = self.qual.tie_back_skill_row_id
        self.assertTrue(row)
        self.assertEqual(row.skill_id, self.skill)
        self.assertTrue(row.is_certification)
        # valid_to = nearest expiry across the closed set (b's).
        self.assertEqual(row.valid_to, self.exp_b)

    def test_rolling_min_updates_in_place(self):
        self._certify(self.emp, self.a, valid_to=self.exp_a)
        cert_b = self._certify(self.emp, self.b, valid_to=self.exp_b)
        self.qual._recompute()
        row = self.qual.tie_back_skill_row_id
        # b recertified further out → min moves to a's expiry, same row.
        cert_b.active = False
        self._certify(self.emp, self.b, valid_to=Date.today() + relativedelta(years=3))
        self.qual._recompute()
        self.assertEqual(self.qual.tie_back_skill_row_id, row)
        self.assertEqual(row.valid_to, self.exp_a)

    def test_suspension_closes_row(self):
        cert_a = self._certify(self.emp, self.a, valid_to=self.exp_a)
        self._certify(self.emp, self.b, valid_to=self.exp_b)
        self.qual._recompute()
        row = self.qual.tie_back_skill_row_id
        cert_a.valid_to = Date.today() - relativedelta(days=1)
        self.qual._recompute()
        self.assertEqual(self.qual.state, "suspended")
        self.assertFalse(self.qual.tie_back_skill_row_id)
        self.assertEqual(row.valid_to, Date.today())  # closed at lapse date

    def test_no_percompetency_rows_in_employee_skill(self):
        self._certify(self.emp, self.a, valid_to=self.exp_a)
        self._certify(self.emp, self.b, valid_to=self.exp_b)
        self.qual._recompute()
        # Only the single coarse tie-back row exists for this employee.
        rows = self.env["hr.employee.skill"].search(
            [("employee_id", "=", self.emp.id)])
        self.assertEqual(rows, self.qual.tie_back_skill_row_id)
