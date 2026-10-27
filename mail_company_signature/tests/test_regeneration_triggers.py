"""Use case: enforced signatures follow the data they are made of.

Acceptance criteria
-------------------
While the policy is enforced, the affected signatures are regenerated when:
* the employee's job position changes (from the employee, or on its current
  ``hr.version``), or its job title changes on the version;
* the job position is renamed in English, in French (``write`` under
  ``lang=fr_FR``) or through the translation dialog
  (``update_field_translations``);
* the company notice or its "Show until" date changes;
* the company name or website changes.
Users of other companies and opted-out users are not touched.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import CompanySignatureCommon

TEMPLATE = (
    "<p>POS:{{job_position}}</p><p>{{company_name}}</p><p>{{company_website}}</p>"
    "<p>{{company_notice}}</p>"
)


@tagged("post_install", "-at_install")
class TestRegenerationTriggers(CompanySignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")
        cls.company_a.sudo().company_signature_template = TEMPLATE
        cls.job = cls.env["hr.job"].create(
            {"name": "Field Technician", "company_id": cls.company_a.id}
        )
        cls.job.update_field_translations("name", {"fr_FR": "Technicien terrain"})
        cls.emp_full = (
            cls.env["hr.employee"]
            .sudo()
            .search([("user_id", "=", cls.u_full.id)], limit=1)
        )
        cls.emp_full.job_id = cls.job

    def setUp(self):
        super().setUp()
        self._enable()

    def test_employee_job_change(self):
        job = self.env["hr.job"].create(
            {"name": "Planner", "company_id": self.company_a.id}
        )
        job.update_field_translations("name", {"fr_FR": "Planificateur"})
        self._employee(self.u_nomobile).write({"job_id": job.id})
        self.assertIn("POS:Planificateur / Planner", self.u_nomobile.signature)

    def test_version_job_and_title_change(self):
        emp = self._employee(self.u_nomobile)
        version = emp.sudo().version_id
        job = self.env["hr.job"].create(
            {"name": "Buyer", "company_id": self.company_a.id}
        )
        version.write({"job_id": job.id})
        self.assertIn("POS:Buyer", self.u_nomobile.signature)
        version.write({"job_id": False, "job_title": "Senior Coordinator"})
        self.assertIn("POS:Senior Coordinator", self.u_nomobile.signature)

    def test_job_rename_en_fr_and_dialog(self):
        self.job.write({"name": "Service Technician"})
        self.assertIn(
            "POS:Technicien terrain / Service Technician", self.u_full.signature
        )
        self.job.with_context(lang="fr_FR").write({"name": "Technicien de service"})
        self.assertIn(
            "POS:Technicien de service / Service Technician", self.u_full.signature
        )
        self.job.update_field_translations("name", {"fr_FR": "Technicien SAV"})
        self.assertIn("POS:Technicien SAV / Service Technician", self.u_full.signature)

    def test_company_notice_and_until(self):
        company = self.company_a.sudo()
        company.company_signature_notice = "<p>Holiday hours</p>"
        self.assertIn("Holiday hours", self.u_full.signature)
        company.company_signature_notice_until = fields.Date.today() - timedelta(
            days=1
        )
        self.assertNotIn("Holiday hours", self.u_full.signature)
        company.company_signature_notice_until = fields.Date.today()
        self.assertIn("Holiday hours", self.u_full.signature)

    def test_company_name_and_website(self):
        self.company_a.sudo().write(
            {"name": "Renamed Test Inc.", "website": "https://renamed.example.com"}
        )
        for user in self.u_full | self.u_nomobile:
            self.assertIn("Renamed Test Inc.", user.signature)
            self.assertIn("https://renamed.example.com", user.signature)
        self.assertIn("Perso", self.u_b.signature)

    def test_opted_out_user_not_touched(self):
        self.u_nomobile.sudo().company_signature_manual = True
        self.u_nomobile.sudo().signature = "<p>my own</p>"
        self.job.write({"name": "Changed"})
        self._employee(self.u_nomobile).write({"job_title": "Changed too"})
        self.company_a.sudo().write({"name": "Renamed Test Inc."})
        self.assertEqual(self.u_nomobile.signature, "<p>my own</p>")
