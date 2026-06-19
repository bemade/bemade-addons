from odoo.tests import common
from odoo import fields, Command
from odoo.exceptions import ValidationError
from datetime import timedelta


class TestPurchaseOrderOverdue(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestPurchaseOrderOverdue, cls).setUpClass()
        cls.env["account.chart.template"].try_loading(
            "generic_coa", company=cls.env.company, install_demo=False
        )

        # Setup d'une société avec des paramètres personnalisés
        cls.company = cls.env.company

        # Créer un partenaire fournisseur avec des factures impayées
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "supplier_rank": 1,
            }
        )

        # Créer une facture fournisseur impayée pour ce fournisseur
        cls.invoice = cls.env["account.move"].create(
            {
                "partner_id": cls.supplier.id,
                "move_type": "in_invoice",
                "invoice_date_due": fields.Date.today() - timedelta(days=20),
                "company_id": cls.company.id,
                "invoice_date": fields.Date.today() - timedelta(days=50),
                "line_ids": [
                    Command.create(
                        {
                            "name": "Test line",
                            "price_unit": 1.00,
                        }
                    )
                ],
            }
        )
        cls.invoice.action_post()

        # Créer un bon de commande pour ce fournisseur
        cls.purchase_order = cls.env["purchase.order"].create(
            {
                "partner_id": cls.supplier.id,
                "company_id": cls.company.id,
            }
        )

    def test_supplier_overdue_invoice_activity_created(self):
        """Teste la création d'une activité 'To-Do' lorsque le fournisseur a des factures en retard"""
        # Confirmer la commande d'achat et vérifier la création de l'activité
        self.purchase_order.button_confirm()

        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "purchase.order"),
                ("res_id", "=", self.purchase_order.id),
                ("user_id", "=", self.env.user.id),
            ]
        )

        # Vérifier qu'une activité a été créée
        self.assertEqual(
            len(activities), 1, "No activity was created for the overdue supplier."
        )

        # Vérifier le contenu de l'activité
        activity = activities[0]
        self.assertEqual(
            activity.summary, "Overdue Invoices for Supplier %s" % self.supplier.name
        )
        self.assertIn(self.supplier.name, activity.note)
        self.assertIn(self.purchase_order.name, activity.note)

    def test_no_activity_for_non_overdue_suppliers(self):
        """Teste qu'aucune activité n'est créée si le fournisseur n'a pas de factures impayées"""
        # Marquer la facture comme payée pour annuler l'état de retard
        self.invoice.payment_state = "paid"

        # Confirmer la commande d'achat
        self.purchase_order.button_confirm()

        # Vérifier qu'aucune activité n'a été créée
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "purchase.order"),
                ("res_id", "=", self.purchase_order.id),
            ]
        )
        self.assertEqual(
            len(activities), 0, "An activity was created despite no overdue invoices."
        )

    def test_activity_for_specific_vendors_only(self):
        """Teste que l'activité est créée seulement pour les fournisseurs spécifiques"""
        # Ajouter le fournisseur à la liste des fournisseurs spécifiques
        self.company.write(
            {
                "warn_supplier_specific_ids": [(4, self.supplier.id)],
                "warn_supplier_scope": "specific",
            }
        )

        # Confirmer la commande d'achat
        self.purchase_order.button_confirm()

        # Vérifier que l'activité a été créée
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "purchase.order"),
                ("res_id", "=", self.purchase_order.id),
                ("user_id", "=", self.env.user.id),
            ]
        )
        self.assertEqual(
            len(activities), 1, "No activity was created for the overdue supplier."
        )

    def test_no_activity_for_non_specific_vendors(self):
        """Teste qu'aucune activité n'est créée si le fournisseur n'est pas dans la liste des fournisseurs spécifiques"""
        # Ne pas inclure le fournisseur dans la liste des fournisseurs spécifiques
        self.company.write(
            {
                "warn_supplier_specific_ids": [(3, self.supplier.id)],
                "warn_supplier_scope": "specific",
            }
        )  # Retirer le fournisseur

        # Confirmer la commande d'achat
        self.purchase_order.button_confirm()

        # Vérifier qu'aucune activité n'a été créée
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "purchase.order"),
                ("res_id", "=", self.purchase_order.id),
            ]
        )
        self.assertEqual(
            len(activities), 0, "An activity was created for a non-specific supplier."
        )
