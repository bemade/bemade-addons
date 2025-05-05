#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from odoo.tests import common, tagged

_logger = logging.getLogger(__name__)

@tagged('post_install', '-at_install')
class TestPortalPartnerManager(common.TransactionCase):
    def setUp(self):
        super(TestPortalPartnerManager, self).setUp()
        
        # Créer une société parente
        self.parent_company = self.env['res.partner'].create({
            'name': 'Test Company',
            'is_company': True,
            'email': 'company@test.com',
            'phone': '+33123456789',
            'street': '123 Test Street',
            'city': 'Test City',
            'zip': '12345',
            'allow_portal_parent_edit': True,
        })
        
        # Créer un contact pour la société
        self.contact = self.env['res.partner'].create({
            'name': 'Test Contact',
            'email': 'contact@test.com',
            'phone': '+33987654321',
            'parent_id': self.parent_company.id,
            'type': 'contact',
        })
        
        # Créer un utilisateur du portail
        self.portal_user = self.env['res.users'].create({
            'name': 'Portal User',
            'login': 'portal_user@test.com',
            'email': 'portal_user@test.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
            'partner_id': self.contact.id,
        })
        
        # Créer une configuration d'accès
        self.access_config = self.env['portal.access'].create({
            'name': 'Test Access Config',
            'partner_id': self.parent_company.id,
            'allow_edit': True,
            'allow_add_contacts': True,
            'portal_user_ids': [(4, self.portal_user.id)],
        })
    
    def test_01_portal_user_access(self):
        """Tester l'accès de l'utilisateur du portail à sa société parente"""
        # Tester en tant qu'utilisateur du portail
        parent_company = self.parent_company.with_user(self.portal_user)
        
        # Vérifier que l'utilisateur peut accéder à sa société parente
        self.assertEqual(parent_company.name, 'Test Company', 
                         "L'utilisateur du portail devrait pouvoir accéder à sa société parente")
    
    def test_02_portal_user_write(self):
        """Tester la modification de la société parente par l'utilisateur du portail"""
        # Tester en tant qu'utilisateur du portail
        parent_company = self.parent_company.with_user(self.portal_user)
        
        # Modifier la société parente
        parent_company.write({
            'name': 'Updated Company Name',
            'email': 'updated@test.com',
        })
        
        # Vérifier que les modifications ont été appliquées
        self.assertEqual(parent_company.name, 'Updated Company Name', 
                         "L'utilisateur du portail devrait pouvoir modifier le nom de sa société parente")
        self.assertEqual(parent_company.email, 'updated@test.com', 
                         "L'utilisateur du portail devrait pouvoir modifier l'email de sa société parente")
        
        # Vérifier que les champs de tracking ont été mis à jour
        self.assertEqual(parent_company.portal_updated_by.id, self.portal_user.id,
                         "Le champ portal_updated_by devrait être mis à jour")
        self.assertTrue(parent_company.portal_last_update, 
                        "Le champ portal_last_update devrait être mis à jour")
    
    def test_03_portal_user_create_contact(self):
        """Tester la création d'un contact par l'utilisateur du portail"""
        # Tester en tant qu'utilisateur du portail
        parent_company = self.parent_company.with_user(self.portal_user)
        
        # Créer un nouveau contact
        new_contact_vals = {
            'name': 'New Contact',
            'email': 'new.contact@test.com',
            'phone': '+33555555555',
        }
        
        new_contact = parent_company.create_portal_contact(parent_company.id, new_contact_vals)
        
        # Vérifier que le contact a été créé correctement
        self.assertEqual(new_contact.name, 'New Contact', 
                         "Le nom du contact devrait être correct")
        self.assertEqual(new_contact.email, 'new.contact@test.com', 
                         "L'email du contact devrait être correct")
        self.assertEqual(new_contact.parent_id.id, parent_company.id, 
                         "Le contact devrait être lié à la société parente")
        
        # Vérifier que les champs de tracking ont été mis à jour
        self.assertEqual(new_contact.portal_updated_by.id, self.portal_user.id,
                         "Le champ portal_updated_by devrait être mis à jour")
        self.assertTrue(new_contact.portal_last_update, 
                        "Le champ portal_last_update devrait être mis à jour")
    
    def test_04_portal_user_access_denied(self):
        """Tester que l'utilisateur du portail ne peut pas accéder à d'autres sociétés"""
        # Créer une autre société
        other_company = self.env['res.partner'].create({
            'name': 'Other Company',
            'is_company': True,
            'email': 'other@test.com',
        })
        
        # Tester en tant qu'utilisateur du portail
        with self.assertRaises(Exception):
            # Essayer de modifier une autre société
            other_company.with_user(self.portal_user).write({
                'name': 'Hacked Company',
            })
    
    def test_05_portal_access_config(self):
        """Tester la configuration d'accès portail"""
        # Désactiver l'accès à la modification
        self.access_config.write({
            'allow_edit': False,
        })
        
        # Vérifier que la société parente a été mise à jour
        self.assertFalse(self.parent_company.allow_portal_parent_edit,
                         "Le champ allow_portal_parent_edit de la société devrait être mis à jour")
        
        # Tester en tant qu'utilisateur du portail
        parent_company = self.parent_company.with_user(self.portal_user)
        
        # Essayer de modifier la société parente (devrait échouer)
        with self.assertRaises(Exception):
            parent_company.write({
                'name': 'Should Not Update',
            })
