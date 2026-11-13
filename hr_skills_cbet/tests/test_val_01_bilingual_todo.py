"""UC-VAL-01 — bilingual expiry to-do title.

The expiry job runs as OdooBot (en_US), so a to-do titled with the user's
language alone always came out in English. Acceptance:

AC1: when a French language is active, the to-do summary reads
     "<French> / <English>" (French first), whatever the language the job
     runs in — e.g. « Certification qui expire : SIM-01 / Certification
     expiring: SIM-01 ».
AC2: with no French language active, the summary stays English only.
AC3: still one to-do per certificate and user — a second run adds nothing.
"""
from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests.common import tagged

from .common import CbetCommon

FRENCH = "Certification qui expire : SIM-01"
ENGLISH = "Certification expiring: SIM-01"


@tagged("post_install", "-at_install")
class TestValBilingualTodo(CbetCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")
        cls.env["ir.module.module"]._load_module_terms(["hr_skills_cbet"], ["fr_FR"])
        mgr_emp = cls.env["hr.employee"].create(
            {"name": "Synthetic Manager", "user_id": cls.manager.id})
        cls.cand = cls.env["hr.employee"].create(
            {"name": "Synthetic Candidate", "parent_id": mgr_emp.id})
        cls.comp = cls._make_competency("SIM-01")

    def _run_cron_en(self):
        self.env["cbet.certification"].with_context(lang="en_US")._cron_expiry_activities()

    def _acts(self, cert):
        return self.env["mail.activity"].search([
            ("res_model", "=", "cbet.certification"), ("res_id", "=", cert.id)])

    def _expiring_cert(self):
        return self._certify(self.cand, self.comp,
                             valid_to=Date.today() + relativedelta(months=1))

    def test_bilingual_title_french_first(self):
        cert = self._expiring_cert()
        self._run_cron_en()
        self.assertEqual(self._acts(cert).summary, f"{FRENCH} / {ENGLISH}")

    def test_english_only_without_french(self):
        self.env["res.lang"].search([("code", "=like", "fr%")]).active = False
        cert = self._expiring_cert()
        self._run_cron_en()
        self.assertEqual(self._acts(cert).summary, ENGLISH)

    def test_no_duplicate_on_second_run(self):
        cert = self._expiring_cert()
        self._run_cron_en()
        self._run_cron_en()
        acts = self._acts(cert)
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts.summary, f"{FRENCH} / {ENGLISH}")
