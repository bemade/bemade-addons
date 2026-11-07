"""French labels of bemade_partner_email_domain.

Acceptance criteria:
- Loading the module's i18n/fr.po for fr_FR translates the "Email Domain"
  field label on res.partner and res.users to « Domaine de courriel ».
- The triage menu reads « Contacts non assignés » and its list header button
  « Appliquer les rattachements ».
- The email domain validation error is raised in French for a French user.
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFrenchTerms(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_FR")
        cls.env["ir.module.module"]._load_module_terms(
            ["bemade_partner_email_domain"], ["fr_FR"], overwrite=True
        )

    def test_email_domain_field_label_in_french(self):
        Fields = self.env["ir.model.fields"].with_context(lang="fr_FR")
        for model in ("res.partner", "res.users"):
            field = Fields._get(model, "email_domain")
            self.assertEqual(field.field_description, "Domaine de courriel", model)

    def test_triage_menu_and_button_in_french(self):
        menu = self.env.ref("bemade_partner_email_domain.menu_partner_parent_suggestion").with_context(lang="fr_FR")
        self.assertEqual(menu.name, "Contacts non assignés")
        arch = (
            self.env["partner.parent.suggestion"]
            .with_context(lang="fr_FR")
            .get_view(self.env.ref("bemade_partner_email_domain.partner_parent_suggestion_view_list").id, "list")["arch"]
        )
        self.assertIn("Appliquer les rattachements", arch)

    def test_validation_error_in_french(self):
        Partner = self.env["res.partner"].with_context(lang="fr_FR")
        with self.assertRaises(ValidationError) as caught:
            Partner.create({"name": "Fr Test", "is_company": True, "email_domain": "gmail.com"})
        self.assertIn("Domaine de courriel invalide", str(caught.exception))
        self.assertIn("fournisseur de messagerie public", str(caught.exception))
