# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from markupsafe import Markup


class TestQuotationAlternativeMigration(TransactionCase):
    """Tests de migration vers Odoo 18.0 pour bemade_quotation_alternative"""

    def setUp(self):
        super().setUp()
        # Créer des données de test
        self.partner = self.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com'
        })
        
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
            'list_price': 100.0,
        })
        
        # Créer un devis original
        self.original_order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'name': 'SO001',
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2,
                'price_unit': 100.0,
            })]
        })

    def test_wizard_creation(self):
        """Test de création du wizard de duplication"""
        wizard = self.env['sale.order.duplication.wizard'].create({
            'original_order_id': self.original_order.id,
            'purpose': 'Test migration Odoo 18',
            'note': '<p>Test note HTML</p>',
        })
        
        self.assertEqual(wizard.original_order_id, self.original_order)
        self.assertTrue(wizard.duplicate_all_lines)
        self.assertEqual(len(wizard.lines_to_duplicate), 1)

    def test_name_generation_logic(self):
        """Test de la logique améliorée de génération des noms"""
        wizard = self.env['sale.order.duplication.wizard'].create({
            'original_order_id': self.original_order.id,
        })
        
        # Le nom généré devrait être SO001-REV1
        self.assertEqual(wizard.new_quot, 'SO001-REV1')
        
        # Créer un devis avec ce nom pour tester l'anti-doublon
        self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'name': 'SO001-REV1',
        })
        
        # Créer un nouveau wizard
        wizard2 = self.env['sale.order.duplication.wizard'].create({
            'original_order_id': self.original_order.id,
        })
        
        # Le nom généré devrait maintenant être SO001-REV2
        self.assertEqual(wizard2.new_quot, 'SO001-REV2')

    def test_markup_compatibility(self):
        """Test de compatibilité Markup() avec Odoo 18"""
        wizard = self.env['sale.order.duplication.wizard'].create({
            'original_order_id': self.original_order.id,
        })
        
        # Simuler la création de messages comme dans action_duplicate_order
        test_markup = Markup(
            "Test message <a href='#' data-oe-model='sale.order' "
            "data-oe-id='%s'>#%s</a> created."
        ) % (self.original_order.id, self.original_order.name)
        
        # Vérifier que Markup fonctionne correctement
        self.assertIsInstance(test_markup, Markup)
        self.assertIn('SO001', str(test_markup))
        self.assertIn('data-oe-model', str(test_markup))

    def test_duplication_all_lines(self):
        """Test de duplication avec toutes les lignes"""
        wizard = self.env['sale.order.duplication.wizard'].create({
            'original_order_id': self.original_order.id,
            'duplicate_all_lines': True,
            'purpose': 'Test duplication complète',
        })
        
        result = wizard.action_duplicate_order()
        
        # Vérifier que l'action retourne bien une fenêtre
        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'sale.order')
        
        # Récupérer le nouveau devis
        new_order = self.env['sale.order'].browse(result['res_id'])
        
        # Vérifications
        self.assertEqual(new_order.partner_id, self.original_order.partner_id)
        self.assertEqual(len(new_order.order_line), len(self.original_order.order_line))
        self.assertEqual(new_order.purpose, 'Test duplication complète')
        self.assertTrue(new_order.name.startswith('SO001-REV'))

    def test_duplication_selective_lines(self):
        """Test de duplication sélective des lignes"""
        # Ajouter une deuxième ligne au devis original
        self.env['sale.order.line'].create({
            'order_id': self.original_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 50.0,
        })
        
        wizard = self.env['sale.order.duplication.wizard'].create({
            'original_order_id': self.original_order.id,
            'duplicate_all_lines': False,
        })
        
        # Désélectionner la première ligne
        wizard.lines_to_duplicate[0].to_duplicate = False
        
        result = wizard.action_duplicate_order()
        new_order = self.env['sale.order'].browse(result['res_id'])
        
        # Vérifier qu'une seule ligne a été dupliquée
        self.assertEqual(len(new_order.order_line), 1)
        self.assertEqual(new_order.order_line.price_unit, 50.0)

    def test_chatter_messages(self):
        """Test des messages dans le chatter"""
        wizard = self.env['sale.order.duplication.wizard'].create({
            'original_order_id': self.original_order.id,
        })
        
        # Compter les messages avant duplication
        original_messages_count = len(self.original_order.message_ids)
        
        result = wizard.action_duplicate_order()
        new_order = self.env['sale.order'].browse(result['res_id'])
        
        # Vérifier que des messages ont été ajoutés
        self.assertGreater(len(self.original_order.message_ids), original_messages_count)
        self.assertGreater(len(new_order.message_ids), 0)
        
        # Vérifier le contenu des messages
        original_last_message = self.original_order.message_ids[0].body
        new_last_message = new_order.message_ids[0].body
        
        self.assertIn('new quotation', original_last_message.lower())
        self.assertIn('duplicating', new_last_message.lower())

    def test_error_handling(self):
        """Test de gestion d'erreurs"""
        # Test avec un devis inexistant
        with self.assertRaises(ValidationError):
            wizard = self.env['sale.order.duplication.wizard'].create({
                'original_order_id': 99999,  # ID inexistant
            })
            wizard.action_duplicate_order()
