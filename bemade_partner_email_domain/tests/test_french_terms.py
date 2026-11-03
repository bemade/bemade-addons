"""French labels of bemade_partner_email_domain.

Acceptance criteria:
- Loading the module's i18n/fr.po for fr_FR translates the "Email Domain"
  field label on res.partner and res.users to « Domaine de courriel ».
"""

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
