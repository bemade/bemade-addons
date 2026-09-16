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
from odoo.tests.common import HttpCase, TransactionCase

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
        content_view = self.env.ref(
            "sale_mandatory_customer_reference"
            ".sale_order_portal_content_inherit_sale_mandatory_reference"
        )
        content_fr = content_view.with_context(lang="fr_CA").arch_db
        self.assertIn("Votre référence (# PO)", content_fr)
        self.assertIn(FR_SENTENCE, content_fr, "hint under the field")
        self.assertIn("Entrez votre numéro de bon de commande", content_fr)

    def test_code_translations_marked_for_fr_ca(self):
        """Odoo 17+ serves code translations only for .po entries carrying the
        '#. odoo-javascript' / '#. odoo-python' comment; without them the JS
        toasts and the ValidationError message stay English."""
        from odoo.tools.translate import code_translations

        web = code_translations.get_web_translations(
            "sale_mandatory_customer_reference", "fr_CA"
        )
        ids = {m["id"] for m in web["messages"]}
        self.assertIn("Reference updated successfully", ids)
        self.assertIn("Failed to save your reference. Please try again.", ids)
        py = code_translations.get_python_translations(
            "sale_mandatory_customer_reference", "fr_CA"
        )
        self.assertIn(
            "Customer reference (PO Number) is required before confirming this order. "
            "Please set the customer reference field.",
            py,
        )



@tagged("post_install", "-at_install")
class TestFrontendTranslations(HttpCase):
    def test_frontend_bundle_includes_this_module(self):
        """The website frontend only bundles JS translations of modules that
        register themselves on ir.http; the portal toasts depend on it."""
        self.env["res.lang"]._activate_lang("fr_CA")
        resp = self.url_open("/website/translations/x?lang=fr_CA")
        data = resp.json()
        self.assertIn("sale_mandatory_customer_reference", data["modules"])
        ids = {m["id"] for m in data["modules"]["sale_mandatory_customer_reference"]["messages"]}
        self.assertIn("Reference updated successfully", ids)
