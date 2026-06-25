# -*- coding: utf-8 -*-

import importlib

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDuplicationExtra(TransactionCase):
    """Couverture additionnelle : action modèle, branches du compute et
    smoke test du script de validation autonome."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Extra Customer", "email": "extra@example.com"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Extra Product", "type": "consu", "list_price": 100.0}
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "name": "SOEXTRA",
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

    def test_action_duplicate_order_returns_wizard_action(self):
        """models/sale_order.py action_duplicate_order : ouvre le wizard avec
        le bon contexte par défaut."""
        action = self.order.action_duplicate_order()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "sale.order.duplication.wizard")
        self.assertEqual(
            action["context"]["default_original_order_id"], self.order.id
        )

    def test_action_duplicate_order_requires_single_record(self):
        """ensure_one() doit lever sur un recordset multiple."""
        order2 = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "name": "SOEXTRA2"}
        )
        multi = self.order | order2
        with self.assertRaises(ValueError):
            multi.action_duplicate_order()

    def test_new_quot_empty_when_no_original(self):
        """_compute_new_quot : branche 'pas de commande originale' -> nom vide."""
        wizard = self.env["sale.order.duplication.wizard"].new({})
        self.assertEqual(wizard.new_quot, "")

    def test_new_quot_without_dash_in_name(self):
        """_compute_new_quot : nom de base sans tiret -> base = nom complet."""
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "name": "PLAINNAME"}
        )
        wizard = self.env["sale.order.duplication.wizard"].create(
            {"original_order_id": order.id}
        )
        self.assertEqual(wizard.new_quot, "PLAINNAME-REV1")

    def test_new_quot_with_dash_strips_suffix(self):
        """_compute_new_quot : nom avec tiret -> on garde seulement la partie
        avant le premier tiret comme base."""
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "name": "BASE-2026"}
        )
        wizard = self.env["sale.order.duplication.wizard"].create(
            {"original_order_id": order.id}
        )
        self.assertEqual(wizard.new_quot, "BASE-REV1")

    def test_migration_validation_smoke(self):
        """Smoke test du script autonome migration_validation.py : il n'est pas
        importé par le module mais reste du code Python valide. On exécute ses
        fonctions de vérification pour s'assurer qu'elles ne lèvent pas."""
        module = importlib.import_module(
            "odoo.addons.bemade_quotation_alternative.migration_validation"
        )

        # Chaque fonction lit de vrais fichiers du module et renvoie un bool.
        self.assertIsInstance(module.check_manifest(), bool)
        self.assertIsInstance(module.check_xml_views(), bool)
        self.assertIsInstance(module.check_python_syntax(), bool)
        self.assertIsInstance(module.check_security(), bool)

        # main() orchestre les quatre vérifications et renvoie un code de sortie.
        self.assertIn(module.main(), (0, 1))
