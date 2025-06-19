# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form


@tagged('post_install', '-at_install')
class TestPortalPlanningModuleIntegration(TransactionCase):
    """Test d'intégration pour les interactions entre le module portal_planning et les autres modules."""

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
        
        # Créer un utilisateur manager
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Manager User',
            'login': 'manager_test_user',
            'email': 'manager_test@example.com',
            'groups_id': [(6, 0, [cls.env.ref('planning.group_planning_manager').id])],
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
        
        # Créer un projet et une tâche pour les feuilles de temps
        cls.project = cls.env['project.project'].create({
            'name': 'Test Project',
        })
        
        cls.task = cls.env['project.task'].create({
            'name': 'Test Task',
            'project_id': cls.project.id,
        })
        
        # Dates pour les tests
        cls.start_datetime = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
        cls.end_datetime = cls.start_datetime + timedelta(hours=4)

    def test_01_planning_module_integration(self):
        """Test de l'intégration avec le module planning."""
        # 1. Créer un créneau de planning via le module planning standard
        slot = self.env['planning.slot'].sudo(self.manager_user).create({
            'name': 'Test Slot',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'allocated_hours': 4.0,
        })
        
        # 2. Vérifier que les champs spécifiques au portail ont été ajoutés
        self.assertIn('portal_status', slot._fields)
        self.assertIn('portal_confirmed', slot._fields)
        self.assertIn('portal_modified', slot._fields)
        self.assertIn('portal_can_confirm', slot._fields)
        self.assertIn('portal_can_modify', slot._fields)
        self.assertIn('portal_can_exchange', slot._fields)
        
        # 3. Vérifier que le statut par défaut est 'draft'
        self.assertEqual(slot.portal_status, 'draft')
        self.assertFalse(slot.portal_confirmed)
        self.assertFalse(slot.portal_modified)
        
        # 4. Vérifier que l'utilisateur portail peut accéder à son créneau
        portal_slot = self.env['planning.slot'].sudo(self.portal_user).search([
            ('id', '=', slot.id)
        ], limit=1)
        
        self.assertTrue(portal_slot, "L'utilisateur portail devrait pouvoir accéder à son créneau")

    def test_02_timesheet_module_integration(self):
        """Test de l'intégration avec le module timesheet."""
        # 1. Créer un créneau de planning avec génération de feuille de temps
        slot = self.env['planning.slot'].sudo().create({
            'name': 'Test Slot',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'allocated_hours': 4.0,
            'portal_status': 'confirmed',
            'portal_confirmed': True,
            'generate_timesheet': True,
            'project_id': self.project.id,
            'task_id': self.task.id,
        })
        
        # 2. Générer la feuille de temps
        slot.sudo().action_generate_timesheet()
        
        # 3. Vérifier qu'une feuille de temps a été créée
        timesheet = self.env['account.analytic.line'].sudo().search([
            ('planning_slot_id', '=', slot.id),
            ('employee_id', '=', self.employee.id),
            ('project_id', '=', self.project.id),
            ('task_id', '=', self.task.id),
        ], limit=1)
        
        self.assertTrue(timesheet, "Une feuille de temps aurait dû être créée")
        self.assertEqual(timesheet.unit_amount, slot.allocated_hours)
        
        # 4. Vérifier que la feuille de temps est liée au créneau de planning
        self.assertEqual(timesheet.planning_slot_id, slot)
        
        # 5. Vérifier que l'utilisateur portail peut voir sa feuille de temps
        portal_timesheet = self.env['account.analytic.line'].sudo(self.portal_user).search([
            ('id', '=', timesheet.id)
        ], limit=1)
        
        self.assertTrue(portal_timesheet, "L'utilisateur portail devrait pouvoir voir sa feuille de temps")

    def test_03_mail_module_integration(self):
        """Test de l'intégration avec le module mail pour les notifications."""
        # 1. Créer une demande de planning
        request = self.env['portal.planning.request'].sudo().create({
            'name': 'Test Planning Request',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'user_id': self.portal_user.id,
            'state': 'draft',
        })
        
        # 2. Vérifier que le modèle hérite de mail.thread
        self.assertTrue(hasattr(request, 'message_post'), "Le modèle devrait hériter de mail.thread")
        
        # 3. Soumettre la demande et vérifier qu'un message est posté
        messages_before = len(request.message_ids)
        request.sudo(self.portal_user).action_submit()
        messages_after = len(request.message_ids)
        
        self.assertTrue(messages_after > messages_before, "Un message devrait être posté lors de la soumission")
        
        # 4. Approuver la demande et vérifier qu'un message est posté
        messages_before = len(request.message_ids)
        request.sudo(self.manager_user).action_approve()
        messages_after = len(request.message_ids)
        
        self.assertTrue(messages_after > messages_before, "Un message devrait être posté lors de l'approbation")

    def test_04_portal_module_integration(self):
        """Test de l'intégration avec le module portal."""
        # 1. Créer un créneau de planning
        slot = self.env['planning.slot'].sudo().create({
            'name': 'Test Slot',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': self.employee.id,
            'allocated_hours': 4.0,
            'portal_status': 'draft',
        })
        
        # 2. Vérifier que le contrôleur du portail est correctement configuré
        # Note: Nous ne pouvons pas tester directement les routes HTTP dans un test unitaire,
        # mais nous pouvons vérifier que les méthodes existent dans le contrôleur
        
        portal_controller = self.env['ir.http']._get_default_lang().sudo()._get_http_routing_module_status()
        self.assertTrue(portal_controller, "Le module portal devrait être installé")
        
        # 3. Vérifier que les règles de sécurité permettent à l'utilisateur portail
        # d'accéder à ses propres créneaux mais pas à ceux des autres
        
        # Créer un autre employé et un créneau associé
        other_employee = self.env['hr.employee'].create({
            'name': 'Other Employee',
        })
        
        other_slot = self.env['planning.slot'].sudo().create({
            'name': 'Other Slot',
            'start_datetime': self.start_datetime,
            'end_datetime': self.end_datetime,
            'role_id': self.role.id,
            'employee_id': other_employee.id,
            'allocated_hours': 4.0,
            'portal_status': 'draft',
        })
        
        # Vérifier l'accès
        own_slots_count = self.env['planning.slot'].sudo(self.portal_user).search_count([
            ('id', '=', slot.id)
        ])
        
        other_slots_count = self.env['planning.slot'].sudo(self.portal_user).search_count([
            ('id', '=', other_slot.id)
        ])
        
        self.assertEqual(own_slots_count, 1, "L'utilisateur portail devrait pouvoir voir son propre créneau")
        self.assertEqual(other_slots_count, 0, "L'utilisateur portail ne devrait pas pouvoir voir le créneau d'un autre employé")
