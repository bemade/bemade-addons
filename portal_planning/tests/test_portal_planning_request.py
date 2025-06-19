# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestPortalPlanningRequest(TransactionCase):
    """Test cases for portal.planning.request model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Créer un utilisateur portail
        cls.portal_user = cls.env['res.users'].create({
            'name': 'Portal User',
            'login': 'portal_test_user',
            'email': 'portal_test@example.com',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        
        # Créer un employé lié à l'utilisateur portail
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'user_id': cls.portal_user.id,
        })
        
        # Créer un rôle de planning
        cls.role = cls.env['planning.role'].create({
            'name': 'Test Role',
        })
        
        # Dates pour les tests
        cls.start_datetime = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
        cls.end_datetime = cls.start_datetime + timedelta(hours=4)

    def test_01_create_planning_request(self):
        """Test la création d'une demande de planning."""
        # Créer une demande de planning
        request = self.env['portal.planning.request'].sudo().create({
            'name': 'Test Planning Request',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'user_id': self.portal_user.id,
            'state': 'draft',
        })
        
        # Vérifier que la demande a été créée correctement
        self.assertEqual(request.name, 'Test Planning Request')
        self.assertEqual(request.state, 'draft')
        self.assertEqual(request.employee_id, self.employee)
        self.assertEqual(request.role_id, self.role)
        
        # Vérifier les heures allouées
        expected_hours = 4.0  # 4 heures entre start_datetime et end_datetime
        self.assertEqual(request.allocated_hours, expected_hours)

    def test_02_submit_planning_request(self):
        """Test la soumission d'une demande de planning."""
        # Créer une demande de planning
        request = self.env['portal.planning.request'].sudo().create({
            'name': 'Test Planning Request',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'user_id': self.portal_user.id,
            'state': 'draft',
        })
        
        # Soumettre la demande
        request.action_submit()
        
        # Vérifier que l'état a changé
        self.assertEqual(request.state, 'submitted')

    def test_03_approve_planning_request(self):
        """Test l'approbation d'une demande de planning."""
        # Créer une demande de planning
        request = self.env['portal.planning.request'].sudo().create({
            'name': 'Test Planning Request',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'user_id': self.portal_user.id,
            'state': 'submitted',  # Déjà soumise
        })
        
        # Approuver la demande
        request.action_approve()
        
        # Vérifier que l'état a changé
        self.assertEqual(request.state, 'approved')
        
        # Vérifier qu'un créneau de planning a été créé
        slot = self.env['planning.slot'].sudo().search([
            ('employee_id', '=', self.employee.id),
            ('start_datetime', '=', self.start_datetime),
            ('end_datetime', '=', self.end_datetime),
        ], limit=1)
        
        self.assertTrue(slot, "Un créneau de planning aurait dû être créé")
        self.assertEqual(slot.role_id, self.role)

    def test_04_reject_planning_request(self):
        """Test le refus d'une demande de planning."""
        # Créer une demande de planning
        request = self.env['portal.planning.request'].sudo().create({
            'name': 'Test Planning Request',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'user_id': self.portal_user.id,
            'state': 'submitted',  # Déjà soumise
        })
        
        # Refuser la demande
        request.action_reject()
        
        # Vérifier que l'état a changé
        self.assertEqual(request.state, 'rejected')

    def test_05_cancel_planning_request(self):
        """Test l'annulation d'une demande de planning."""
        # Créer une demande de planning
        request = self.env['portal.planning.request'].sudo().create({
            'name': 'Test Planning Request',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'user_id': self.portal_user.id,
            'state': 'draft',
        })
        
        # Annuler la demande
        request.action_cancel()
        
        # Vérifier que l'état a changé
        self.assertEqual(request.state, 'cancelled')

    def test_06_reset_to_draft_planning_request(self):
        """Test la remise en brouillon d'une demande de planning."""
        # Créer une demande de planning
        request = self.env['portal.planning.request'].sudo().create({
            'name': 'Test Planning Request',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'user_id': self.portal_user.id,
            'state': 'rejected',  # Déjà refusée
        })
        
        # Remettre en brouillon
        request.action_reset_to_draft()
        
        # Vérifier que l'état a changé
        self.assertEqual(request.state, 'draft')

    def test_07_validation_end_datetime_after_start_datetime(self):
        """Test la validation que la date de fin est après la date de début."""
        # Essayer de créer une demande avec une date de fin avant la date de début
        with self.assertRaises(ValidationError):
            self.env['portal.planning.request'].sudo().create({
                'name': 'Test Planning Request',
                'start_datetime': self.start_datetime,
                'end_datetime': self.start_datetime - timedelta(hours=1),  # Date de fin avant la date de début
                'role_id': self.role.id,
                'employee_id': self.employee.id,
                'user_id': self.portal_user.id,
                'state': 'draft',
            })

    def test_08_compute_allocated_hours(self):
        """Test le calcul des heures allouées."""
        # Créer une demande de planning avec une durée spécifique
        duration_hours = 6
        request = self.env['portal.planning.request'].sudo().create({
            'name': 'Test Planning Request',
            'start_datetime': self.start_datetime,
            'end_datetime': self.start_datetime + timedelta(hours=duration_hours),
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'user_id': self.portal_user.id,
            'state': 'draft',
        })
        
        # Vérifier que les heures allouées sont correctement calculées
        self.assertEqual(request.allocated_hours, float(duration_hours))
