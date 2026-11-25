"""UC-VAL-01 — Expiry engine.

AC2: daily cron creates activities for expiring/expired competency certifications,
     assignee = employee's manager (parent_id), once per certification.
AC4: expiry suspends qualifications in the closed set.
AC5: when the company names an HR responsible (cbet_hr_responsible_id), each
     expiring/expired certification also gets one to-do for that user (none
     extra when it is the manager); re-running the cron never duplicates.
"""
from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestValExpiry(CbetCommon):
    def setUp(self):
        super().setUp()
        self.mgr_emp = self.env["hr.employee"].create(
            {"name": "Manager Emp", "user_id": self.manager.id})
        self.cand = self.env["hr.employee"].create(
            {"name": "Cand V", "parent_id": self.mgr_emp.id})
        self.comp = self._make_competency("VAL-01")

    def _model(self):
        return self.env["cbet.certification"]

    def test_activity_to_manager_and_dedup(self):
        self._certify(self.cand, self.comp,
                      valid_to=Date.today() + relativedelta(months=1))
        self._model()._cron_expiry_activities()
        cert = self._model().search(
            [("employee_id", "=", self.cand.id), ("competency_id", "=", self.comp.id)])
        acts = self.env["mail.activity"].search([
            ("res_model", "=", "cbet.certification"), ("res_id", "=", cert.id)])
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts.user_id, self.manager)
        # Re-run → no duplicate activity (AC2 once per certification).
        self._model()._cron_expiry_activities()
        self.assertEqual(len(self.env["mail.activity"].search(
            [("res_model", "=", "cbet.certification"), ("res_id", "=", cert.id)])), 1)

    def test_expiry_suspends_qualification(self):
        skill = self._make_cert_skill("Tech Classe I")
        std = self._make_standard("Classe I", essentials=self.comp, skill=skill)
        cert = self._certify(self.cand, self.comp,
                             valid_to=Date.today() + relativedelta(months=1))
        qual = self.env["cbet.qualification"]._get_or_create(self.cand, std)
        qual._recompute()
        self.assertEqual(qual.state, "qualified")
        # Cert lapses; cron recomputes → suspended.
        cert.valid_to = Date.today() - relativedelta(days=1)
        self._model()._cron_expiry_activities()
        self.assertEqual(qual.state, "suspended")

    def _acts(self, cert):
        return self.env["mail.activity"].search([
            ("res_model", "=", "cbet.certification"), ("res_id", "=", cert.id)])

    def test_hr_responsible_gets_a_todo_too(self):
        hr_user = self.env["res.users"].create({
            "name": "Synthetic HR", "login": "cbet_synth_hr",
            "email": "cbet_synth_hr@example.com"})
        self.env.company.cbet_hr_responsible_id = hr_user
        cert = self._certify(self.cand, self.comp,
                             valid_to=Date.today() + relativedelta(months=1))
        self._model()._cron_expiry_activities()
        self.assertEqual(self._acts(cert).user_id, self.manager | hr_user)
        self.assertEqual(len(self._acts(cert)), 2)
        self._model()._cron_expiry_activities()
        self.assertEqual(len(self._acts(cert)), 2)

    def test_hr_responsible_set_after_first_run(self):
        cert = self._certify(self.cand, self.comp,
                             valid_to=Date.today() - relativedelta(days=2))
        self._model()._cron_expiry_activities()
        self.assertEqual(self._acts(cert).user_id, self.manager)
        hr_user = self.env["res.users"].create({
            "name": "Synthetic HR 2", "login": "cbet_synth_hr2",
            "email": "cbet_synth_hr2@example.com"})
        self.env.company.cbet_hr_responsible_id = hr_user
        self._model()._cron_expiry_activities()
        self.assertEqual(self._acts(cert).user_id, self.manager | hr_user)
        self.assertEqual(len(self._acts(cert)), 2)

    def test_hr_responsible_same_as_manager(self):
        self.env.company.cbet_hr_responsible_id = self.manager
        cert = self._certify(self.cand, self.comp,
                             valid_to=Date.today() + relativedelta(months=1))
        self._model()._cron_expiry_activities()
        self.assertEqual(len(self._acts(cert)), 1)
