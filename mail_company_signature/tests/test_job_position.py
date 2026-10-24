"""Use case: show the employee's job position in French and English.

Acceptance criteria
-------------------
* ``{{job_position}}`` renders the job position's French (fr_FR) and English
  (en_US) names as "FR / EN".
* One value only when both names are equal, or when the French translation is
  missing (it then falls back to the English source).
* Surrounding spaces of the names are ignored.
* Without a job position, ``{{job_position}}`` falls back to the employee's job
  title; with neither, its paragraph is removed (existing empty-line rule).
* ``{{job_title}}`` keeps its meaning: the employee's job title as typed.
* Values are HTML-escaped.
* The language of the user does not matter.
"""

from odoo.tests import tagged

from .common import CompanySignatureCommon

TEMPLATE = (
    "<p>{{name}}</p><p>POS:{{job_position}}</p><p>TITLE:{{job_title}}</p>"
    "<p>{{company_name}}</p>"
)


@tagged("post_install", "-at_install")
class TestJobPosition(CompanySignatureCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")
        cls.company_a.sudo().company_signature_template = TEMPLATE
        cls.job = cls.env["hr.job"].create(
            {"name": "Field Technician", "company_id": cls.company_a.id}
        )
        cls.job.update_field_translations("name", {"fr_FR": "Technicien terrain"})
        cls.emp_full = cls._employee_of(cls.u_full)
        cls.emp_full.job_id = cls.job

    @classmethod
    def _employee_of(cls, user):
        return (
            cls.env["hr.employee"].sudo().search([("user_id", "=", user.id)], limit=1)
        )

    def test_french_and_english(self):
        self._enable()
        self.assertIn(
            "<p>POS:Technicien terrain / Field Technician</p>", self.u_full.signature
        )

    def test_single_value_when_equal_or_missing(self):
        self._enable()
        for translations in ({"fr_FR": "Field Technician"}, {"fr_FR": False}):
            with self.subTest(translations=translations):
                self.job.update_field_translations("name", translations)
                self.assertIn("<p>POS:Field Technician</p>", self.u_full.signature)

    def test_names_are_stripped(self):
        self.job.update_field_translations("name", {"fr_FR": " Technicien terrain "})
        self._enable()
        self.assertIn(
            "<p>POS:Technicien terrain / Field Technician</p>", self.u_full.signature
        )

    def test_fallback_to_job_title_then_dropped(self):
        self._enable()
        # u_nomobile has a job title and no job position
        self.assertIn("<p>POS:Technicien</p>", self.u_nomobile.signature)
        # an employee with neither: the line is removed, label included
        self._make_employee(self.u_noemp, self.company_a)
        self.assertIn("Sig sig_noemp", self.u_noemp.signature)
        self.assertNotIn("POS:", self.u_noemp.signature)

    def test_job_title_placeholder_unchanged(self):
        self.emp_full.job_title = "Custom Title"
        self._enable()
        sig = self.u_full.signature
        self.assertIn("<p>TITLE:Custom Title</p>", sig)
        self.assertIn("<p>POS:Technicien terrain / Field Technician</p>", sig)

    def test_values_are_escaped(self):
        self.job.update_field_translations(
            "name", {"en_US": "R&D <b>lead</b>", "fr_FR": "R&D <b>chef</b>"}
        )
        self._enable()
        sig = self.u_full.signature
        self.assertIn("R&amp;D &lt;b&gt;chef&lt;/b&gt; / R&amp;D &lt;b&gt;lead", sig)
        self.assertNotIn("<b>", sig)

    def test_user_language_irrelevant(self):
        self.u_full.lang = "fr_FR"
        self._enable()
        self.assertIn(
            "<p>POS:Technicien terrain / Field Technician</p>",
            self.u_full.with_context(lang="fr_FR").signature,
        )
