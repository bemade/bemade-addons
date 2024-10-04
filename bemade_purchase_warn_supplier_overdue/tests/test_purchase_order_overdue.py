from odoo.tests import common
from odoo import fields
from odoo.exceptions import ValidationError


class TestPurchaseOrderOverdue(common.TransactionCase):

    def setUp(self):
        super(TestPurchaseOrderOverdue, self).setUp()

        # Setup d'une société avec des paramètres personnalisés
        self.company = self.env['res.company'].create({
            'name': 'Test Company',
            'warn_supplier_overdue': True,
            'warn_supplier_overdue_user_type': 'specific',
            'warn_supplier_overdue_user_id': self.env.user.id,  # L'utilisateur courant
            'warn_supplier_scope': 'specific',
        })

        # Créer un partenaire fournisseur avec des factures impayées
        self.supplier = self.env['res.partner'].create({
            'name': 'Test Supplier',
            'supplier_rank': 1,
        })

        # Créer une facture fournisseur impayée pour ce fournisseur
        self.invoice = self.env['account.move'].create({
            'partner_id': self.supplier.id,
            'move_type': 'in_invoice',
            'invoice_date_due': fields.Date.today(),
            'company_id': self.company.id,
        })

        # Créer un bon de commande pour ce fournisseur
        self.purchase_order = self.env['purchase.order'].create({
            'partner_id': self.supplier.id,
            'company_id': self.company.id,
        })

    def test_supplier_overdue_invoice_activity_created(self):
        """ Teste la création d'une activité 'To-Do' lorsque le fournisseur a des factures en retard """
        # Confirmer la commande d'achat et vérifier la création de l'activité
        self.purchase_order.button_confirm()

        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', self.purchase_order.id),
            ('user_id', '=', self.env.user.id)
        ])

        # Vérifier qu'une activité a été créée
        self.assertEqual(len(activities), 1, 'No activity was created for the overdue supplier.')

        # Vérifier le contenu de l'activité
        activity = activities[0]
        self.assertEqual(activity.summary, 'Overdue Invoices for Supplier %s' % self.supplier.name)
        self.assertIn(self.supplier.name, activity.note)
        self.assertIn(self.purchase_order.name, activity.note)

    def test_no_activity_for_non_overdue_suppliers(self):
        """ Teste qu'aucune activité n'est créée si le fournisseur n'a pas de factures impayées """
        # Marquer la facture comme payée pour annuler l'état de retard
        self.invoice.action_post()
        self.invoice.button_mark_as_paid()

        # Confirmer la commande d'achat
        self.purchase_order.button_confirm()

        # Vérifier qu'aucune activité n'a été créée
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', self.purchase_order.id),
        ])
        self.assertEqual(len(activities), 0, 'An activity was created despite no overdue invoices.')

    def test_activity_for_specific_vendors_only(self):
        """ Teste que l'activité est créée seulement pour les fournisseurs spécifiques """
        # Ajouter le fournisseur à la liste des fournisseurs spécifiques
        self.company.write({'warn_supplier_specific_ids': [(4, self.supplier.id)]})

        # Confirmer la commande d'achat
        self.purchase_order.button_confirm()

        # Vérifier que l'activité a été créée
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', self.purchase_order.id),
            ('user_id', '=', self.env.user.id)
        ])
        self.assertEqual(len(activities), 1, 'No activity was created for the overdue supplier.')

    def test_no_activity_for_non_specific_vendors(self):
        """ Teste qu'aucune activité n'est créée si le fournisseur n'est pas dans la liste des fournisseurs spécifiques """
        # Ne pas inclure le fournisseur dans la liste des fournisseurs spécifiques
        self.company.write({'warn_supplier_specific_ids': [(3, self.supplier.id)]})  # Retirer le fournisseur

        # Confirmer la commande d'achat
        self.purchase_order.button_confirm()

        # Vérifier qu'aucune activité n'a été créée
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'purchase.order'),
            ('res_id', '=', self.purchase_order.id),
        ])
        self.assertEqual(len(activities), 0, 'An activity was created for a non-specific supplier.')