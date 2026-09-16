# License: LGPL-3
# Copyright 2026 Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""
The portal "reference required" warning must translate like the rest of the
page. QWeb builds one translation term per inline run, and <i> is an inline
element (odoo.tools.translate.TRANSLATED_ELEMENTS), so an icon placed in the
same run as the sentence changes the msgid and the fr_CA entry no longer
matches.

Acceptance criteria:
- AC1: with fr_CA loaded, the sidebar/bottom warning views carry the French
  sentence in their fr_CA arch.
"""
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

FR_SENTENCE = "Une référence (numéro de bon de commande) est requise"


@tagged("post_install", "-at_install")
class TestPortalAlertI18n(TransactionCase):
    def test_reference_alert_translated_fr_ca(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["sale_mandatory_customer_reference"], ["fr_CA"], overwrite=True
        )
        view = self.env.ref(
            "sale_mandatory_customer_reference"
            ".sale_order_portal_template_inherit_sale_mandatory_reference"
        )
        arch_fr = view.with_context(lang="fr_CA").arch_db
        self.assertIn("o_portal_reference_alert", arch_fr)
        self.assertEqual(
            arch_fr.count(FR_SENTENCE),
            2,
            "both reference warnings (sidebar + bottom) must be translated",
        )
