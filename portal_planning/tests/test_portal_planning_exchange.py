# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestPortalPlanningExchange(TransactionCase):
    """Test cases for portal.planning.exchange model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Créer un utilisateur portail source
        cls.portal_user_source = cls.env['res.users'].create({
            'name': 'Portal User Source',
            'login': 'portal_source_user',
            'email': 'portal_source@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        
        # Créer un utilisateur portail cible
        cls.portal_user_target = cls.env['res.users'].create({
            'name': 'Portal User Target',
            'login': 'portal_target_user',
            'email': 'portal_target@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        
        # Créer des employés liés aux utilisateurs portail
        cls.employee_source = cls.env['hr.employee'].create({
            'name': 'Source Employee',
            'user_id': cls.portal_user_source.id,
        })
        
        cls.employee_target = cls.env['hr.employee'].create({
            'name': 'Target Employee',
            'user_id': cls.portal_user_target.id,
        })
        
        # Créer un rôle de planning
        cls.role = cls.env['planning.role'].create({
            'name': 'Test Role',
        })
        
        # Dates pour les tests
        cls.start_datetime_source = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
        cls.end_datetime_source = cls.start_datetime_source + timedelta(hours=4)
        
        cls.start_datetime_target = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
        cls.end_datetime_target = cls.start_datetime_target + timedelta(hours=4)
        
        # Créer des créneaux de planning
        cls.slot_source = cls.env['planning.slot'].sudo().create({
            'name': 'Source Slot',
            'start_datetime': cls.start_datetime_source,
            'end_datetime': cls.end_datetime_source,
            'role_id': cls.role.id,
            'employee_id': cls.employee_source.id,
            'allocated_hours': 4.0,
        })
        
        cls.slot_target = cls.env['planning.slot'].sudo().create({
            'name': 'Target Slot',
            'start_datetime': cls.start_datetime_target,
            'end_datetime': cls.end_datetime_target,
            'role_id': cls.role.id,
            'employee_id': cls.employee_target.id,
            'allocated_hours': 4.0,
        })

    def test_01_create_exchange_request(self):
        """Test la création d'une demande d'échange."""
        # Créer une demande d'échange
        exchange = self.env['portal.planning.exchange'].sudo().create({
            'name': 'Test Exchange Request',
            'source_slot_id': self.slot_source.id,
            'target_slot_id': self.slot_target.id,
            'source_user_id': self.portal_user_source.id,
            'target_user_id': self.portal_user_target.id,
            'state': 'draft',
            'reason': 'Test reason',
        })
        
        # Vérifier que la demande a été créée correctement
        self.assertEqual(exchange.name, 'Test Exchange Request')
        self.assertEqual(exchange.state, 'draft')
        self.assertEqual(exchange.source_slot_id, self.slot_source)
        self.assertEqual(exchange.target_slot_id, self.slot_target)
        self.assertEqual(exchange.source_user_id, self.portal_user_source)
        self.assertEqual(exchange.target_user_id, self.portal_user_target)

    def test_02_submit_exchange_request(self):
        """Test la soumission d'une demande d'échange."""
        # Créer une demande d'échange
        exchange = self.env['portal.planning.exchange'].sudo().create({
            'name': 'Test Exchange Request',
            'source_slot_id': self.slot_source.id,
            'target_slot_id': self.slot_target.id,
            'source_user_id': self.portal_user_source.id,
            'target_user_id': self.portal_user_target.id,
            'state': 'draft',
            'reason': 'Test reason',
        })
        
        # Soumettre la demande
        exchange.action_submit()
        
        # Vérifier que l'état a changé
        self.assertEqual(exchange.state, 'pending')

    def test_03_approve_exchange_request(self):
        """Test l'approbation d'une demande d'échange."""
        # Créer une demande d'échange
        exchange = self.env['portal.planning.exchange'].sudo().create({
            'name': 'Test Exchange Request',
            'source_slot_id': self.slot_source.id,
            'target_slot_id': self.slot_target.id,
            'source_user_id': self.portal_user_source.id,
            'target_user_id': self.portal_user_target.id,
            'state': 'pending',  # Déjà en attente
            'reason': 'Test reason',
        })
        
        # Approuver la demande
        exchange.action_approve()
        
        # Vérifier que l'état a changé
        self.assertEqual(exchange.state, 'approved')
        
        # Vérifier que les employés des créneaux ont été échangés
        self.slot_source.refresh()
        self.slot_target.refresh()
        
        self.assertEqual(self.slot_source.employee_id, self.employee_target)
        self.assertEqual(self.slot_target.employee_id, self.employee_source)

    def test_04_reject_exchange_request(self):
        """Test le refus d'une demande d'échange."""
        # Créer une demande d'échange
        exchange = self.env['portal.planning.exchange'].sudo().create({
            'name': 'Test Exchange Request',
            'source_slot_id': self.slot_source.id,
            'target_slot_id': self.slot_target.id,
            'source_user_id': self.portal_user_source.id,
            'target_user_id': self.portal_user_target.id,
            'state': 'pending',  # Déjà en attente
            'reason': 'Test reason',
        })
        
        # Refuser la demande
        exchange.action_reject()
        
        # Vérifier que l'état a changé
        self.assertEqual(exchange.state, 'rejected')
        
        # Vérifier que les employés des créneaux n'ont pas été échangés
        self.slot_source.refresh()
        self.slot_target.refresh()
        
        self.assertEqual(self.slot_source.employee_id, self.employee_source)
        self.assertEqual(self.slot_target.employee_id, self.employee_target)

    def test_05_cancel_exchange_request(self):
        """Test l'annulation d'une demande d'échange."""
        # Créer une demande d'échange
        exchange = self.env['portal.planning.exchange'].sudo().create({
            'name': 'Test Exchange Request',
            'source_slot_id': self.slot_source.id,
            'target_slot_id': self.slot_target.id,
            'source_user_id': self.portal_user_source.id,
            'target_user_id': self.portal_user_target.id,
            'state': 'draft',
            'reason': 'Test reason',
        })
        
        # Annuler la demande
        exchange.action_cancel()
        
        # Vérifier que l'état a changé
        self.assertEqual(exchange.state, 'cancelled')

    def test_06_validation_different_employees(self):
        """Test la validation que les employés source et cible sont différents."""
        # Créer un créneau avec le même employé que le créneau source
        slot_same_employee = self.env['planning.slot'].sudo().create({
            'name': 'Same Employee Slot',
            'start_datetime': self.start_datetime_target,
            'end_datetime': self.end_datetime_target,
            'role_id': self.role.id,
            'employee_id': self.employee_source.id,  # Même employé que le créneau source
            'allocated_hours': 4.0,
        })
        
        # Essayer de créer une demande d'échange avec le même employé
        with self.assertRaises(ValidationError):
            self.env['portal.planning.exchange'].sudo().create({
                'name': 'Test Exchange Request',
                'source_slot_id': self.slot_source.id,
                'target_slot_id': slot_same_employee.id,  # Créneau avec le même employé
                'source_user_id': self.portal_user_source.id,
                'target_user_id': self.portal_user_source.id,  # Même utilisateur
                'state': 'draft',
                'reason': 'Test reason',
            })

    def test_07_compute_name(self):
        """Test le calcul automatique du nom de la demande d'échange."""
        # Créer une demande d'échange sans nom
        exchange = self.env['portal.planning.exchange'].sudo().create({
            'source_slot_id': self.slot_source.id,
            'target_slot_id': self.slot_target.id,
            'source_user_id': self.portal_user_source.id,
            'target_user_id': self.portal_user_target.id,
            'state': 'draft',
            'reason': 'Test reason',
        })
        
        # Vérifier que le nom a été généré automatiquement
        expected_name = f"Échange: {self.slot_source.name} <-> {self.slot_target.name}"
        self.assertEqual(exchange.name, expected_name)
