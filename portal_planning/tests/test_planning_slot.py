# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestPlanningSlot(TransactionCase):
    """Test cases for planning.slot model extended for portal access."""

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
        
        # Créer un créneau de planning
        cls.slot = cls.env['planning.slot'].sudo().create({
            'name': 'Test Slot',
            'start_datetime': cls.start_datetime,
            'end_datetime': cls.end_datetime,
            'role_id': cls.role.id,
            'employee_id': cls.employee.id,
            'allocated_hours': 4.0,
            'portal_status': 'draft',
            'portal_confirmed': False,
            'portal_modified': False,
        })

    def test_01_confirm_slot_portal(self):
        """Test la confirmation d'un créneau via le portail."""
        # Confirmer le créneau
        self.slot.action_confirm_portal()
        
        # Vérifier que le statut a changé
        self.assertEqual(self.slot.portal_status, 'confirmed')
        self.assertTrue(self.slot.portal_confirmed)
        self.assertFalse(self.slot.portal_modified)

    def test_02_modify_slot_portal(self):
        """Test la modification d'un créneau via le portail."""
        # Nouvelles valeurs pour la modification
        new_start = self.start_datetime + timedelta(hours=1)
        new_end = self.end_datetime + timedelta(hours=1)
        
        # Modifier le créneau
        self.slot.write({
            'portal_start_datetime': new_start,
            'portal_end_datetime': new_end,
            'portal_modified': True,
            'portal_status': 'modified',
        })
        
        # Vérifier que les valeurs de modification ont été enregistrées
        self.assertEqual(self.slot.portal_start_datetime, new_start)
        self.assertEqual(self.slot.portal_end_datetime, new_end)
        self.assertTrue(self.slot.portal_modified)
        self.assertEqual(self.slot.portal_status, 'modified')
        
        # Approuver la modification
        self.slot.action_approve_modification()
        
        # Vérifier que les valeurs ont été appliquées au créneau
        self.assertEqual(self.slot.start_datetime, new_start)
        self.assertEqual(self.slot.end_datetime, new_end)
        self.assertEqual(self.slot.portal_status, 'confirmed')
        self.assertTrue(self.slot.portal_confirmed)
        self.assertFalse(self.slot.portal_modified)

    def test_03_reject_modification(self):
        """Test le rejet d'une modification de créneau."""
        # Nouvelles valeurs pour la modification
        new_start = self.start_datetime + timedelta(hours=1)
        new_end = self.end_datetime + timedelta(hours=1)
        
        # Modifier le créneau
        self.slot.write({
            'portal_start_datetime': new_start,
            'portal_end_datetime': new_end,
            'portal_modified': True,
            'portal_status': 'modified',
        })
        
        # Rejeter la modification
        self.slot.action_reject_modification()
        
        # Vérifier que les valeurs originales sont conservées
        self.assertEqual(self.slot.start_datetime, self.start_datetime)
        self.assertEqual(self.slot.end_datetime, self.end_datetime)
        self.assertEqual(self.slot.portal_status, 'draft')
        self.assertFalse(self.slot.portal_confirmed)
        self.assertFalse(self.slot.portal_modified)

    def test_04_generate_timesheet(self):
        """Test la génération de feuille de temps à partir d'un créneau."""
        # Activer la génération de feuilles de temps
        self.slot.write({
            'generate_timesheet': True,
            'portal_status': 'confirmed',
            'portal_confirmed': True,
        })
        
        # Générer la feuille de temps
        self.slot.action_generate_timesheet()
        
        # Vérifier qu'une feuille de temps a été créée
        timesheet = self.env['account.analytic.line'].sudo().search([
            ('planning_slot_id', '=', self.slot.id),
            ('employee_id', '=', self.employee.id),
        ], limit=1)
        
        self.assertTrue(timesheet, "Une feuille de temps aurait dû être créée")
        self.assertEqual(timesheet.unit_amount, self.slot.allocated_hours)

    def test_05_compute_can_modify(self):
        """Test le calcul du champ portal_can_modify."""
        # Par défaut, un créneau en brouillon peut être modifié
        self.assertTrue(self.slot.portal_can_modify)
        
        # Un créneau confirmé ne peut pas être modifié
        self.slot.write({
            'portal_status': 'confirmed',
            'portal_confirmed': True,
        })
        self.assertFalse(self.slot.portal_can_modify)
        
        # Un créneau déjà modifié ne peut pas être modifié à nouveau
        self.slot.write({
            'portal_status': 'modified',
            'portal_modified': True,
            'portal_confirmed': False,
        })
        self.assertFalse(self.slot.portal_can_modify)

    def test_06_compute_can_confirm(self):
        """Test le calcul du champ portal_can_confirm."""
        # Par défaut, un créneau en brouillon peut être confirmé
        self.assertTrue(self.slot.portal_can_confirm)
        
        # Un créneau déjà confirmé ne peut pas être confirmé à nouveau
        self.slot.write({
            'portal_status': 'confirmed',
            'portal_confirmed': True,
        })
        self.assertFalse(self.slot.portal_can_confirm)
        
        # Un créneau modifié ne peut pas être confirmé
        self.slot.write({
            'portal_status': 'modified',
            'portal_modified': True,
            'portal_confirmed': False,
        })
        self.assertFalse(self.slot.portal_can_confirm)

    def test_07_compute_can_exchange(self):
        """Test le calcul du champ portal_can_exchange."""
        # Par défaut, un créneau peut être échangé
        self.assertTrue(self.slot.portal_can_exchange)
        
        # Un créneau avec une demande d'échange en cours ne peut pas être échangé à nouveau
        exchange = self.env['portal.planning.exchange'].sudo().create({
            'name': 'Test Exchange',
            'source_slot_id': self.slot.id,
            'source_user_id': self.portal_user.id,
            'state': 'pending',
        })
        
        # Rafraîchir le créneau pour recalculer les champs calculés
        self.slot.refresh()
        
        # Vérifier que le créneau ne peut plus être échangé
        self.assertFalse(self.slot.portal_can_exchange)
        
        # Annuler la demande d'échange
        exchange.action_cancel()
        
        # Rafraîchir le créneau pour recalculer les champs calculés
        self.slot.refresh()
        
        # Vérifier que le créneau peut à nouveau être échangé
        self.assertTrue(self.slot.portal_can_exchange)
