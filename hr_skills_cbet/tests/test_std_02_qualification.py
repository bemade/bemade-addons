"""UC-STD-02 — Employee qualification state.

AC1: qualified iff every competency in the closed set has a currently valid cert.
AC2: progress metrics (n certified / n required, % complete).
AC3: a lapse flips qualification to suspended (not lost); recert restores it.
"""
from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestStdQualification(CbetCommon):
    def setUp(self):
        super().setUp()
        self.a = self._make_competency("STD-10")
        self.b = self._make_competency("STD-11")
        self.env["cbet.prerequisite"].create(
            {"competency_id": self.a.id, "prerequisite_id": self.b.id,
             "prereq_type": "obligatoire"})
        self.std = self._make_standard("Classe I", essentials=self.a)
        self.emp = self._make_employee("Tech A")
        self.qual = self.env["cbet.qualification"]._get_or_create(self.emp, self.std)
        self.future = Date.today() + relativedelta(years=1)

    def test_partial_is_in_progress(self):
        self._certify(self.emp, self.a, valid_to=self.future)
        self.qual._recompute()
        self.assertEqual(self.qual.state, "in_progress")
        self.assertEqual(self.qual.n_required, 2)
        self.assertEqual(self.qual.n_certified, 1)
        self.assertEqual(self.qual.percent_complete, 50.0)

    def test_full_is_qualified(self):
        self._certify(self.emp, self.a, valid_to=self.future)
        self._certify(self.emp, self.b, valid_to=self.future)
        self.qual._recompute()
        self.assertEqual(self.qual.state, "qualified")
        self.assertEqual(self.qual.percent_complete, 100.0)

    def test_lapse_suspends_then_recert_restores(self):
        cert_a = self._certify(self.emp, self.a, valid_to=self.future)
        self._certify(self.emp, self.b, valid_to=self.future)
        self.qual._recompute()
        self.assertEqual(self.qual.state, "qualified")

        # a lapses (expired yesterday).
        cert_a.valid_to = Date.today() - relativedelta(days=1)
        self.qual._recompute()
        self.assertEqual(self.qual.state, "suspended")

        # recertify a → restored without touching b.
        self._certify(self.emp, self.a, valid_to=self.future)
        cert_a.active = False
        self.qual._recompute()
        self.assertEqual(self.qual.state, "qualified")
