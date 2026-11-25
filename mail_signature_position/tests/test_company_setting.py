"""Use case: an administrator chooses, per company, where the signature goes.

Acceptance criteria
-------------------
* A new company defaults to ``below`` (Odoo's standard layout).
* The value is stored per company: changing it on one company does not change
  it on another.
* An administrator can change it from Settings (``res.config.settings``) and
  the change lands on the current company only.
* The field is exposed in the Settings form view (Discuss block).
"""

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompanySetting(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Signature Co B"})

    def test_default_is_below(self):
        company = self.env["res.company"].create({"name": "Signature Co New"})
        self.assertEqual(company.mail_signature_position, "below")

    def test_value_is_per_company(self):
        self.company_a.mail_signature_position = "above"
        self.assertEqual(self.company_a.mail_signature_position, "above")
        self.assertEqual(self.company_b.mail_signature_position, "below")

    def test_admin_sets_it_from_settings(self):
        settings = self.env["res.config.settings"].with_company(self.company_b)
        with Form(settings) as form:
            self.assertEqual(form.mail_signature_position, "below")
            form.mail_signature_position = "above"
        self.assertEqual(self.company_b.mail_signature_position, "above")
        self.assertEqual(self.company_a.mail_signature_position, "below")

    def test_field_is_in_settings_view(self):
        arch = self.env["res.config.settings"].get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertIn('name="mail_signature_position"', arch)
