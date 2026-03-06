# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError
from datetime import datetime, timedelta


class TestProjectTaskPortalSecurity(TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        # Create test users
        self.portal_tp_user = self.env['res.users'].create({
            'name': 'Portal Treatment Professional',
            'login': 'portal_tp_test',
            'email': 'portal_tp@test.com',
            'groups_id': [(4, self.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id)]
        })
        
        self.regular_portal_user = self.env['res.users'].create({
            'name': 'Regular Portal User',
            'login': 'portal_regular_test',
            'email': 'portal_regular@test.com',
            'groups_id': [(4, self.env.ref('base.group_portal').id)]
        })
        
        # Create test project with portal access
        self.test_project = self.env['project.project'].create({
            'name': 'Test Sports Project',
            'privacy_visibility': 'portal',
            'is_sports_clinic_project': True,
        })
        
        # Add portal TP as follower
        self.test_project.message_subscribe(partner_ids=[self.portal_tp_user.partner_id.id])
        
        # Create test task
        self.test_task = self.env['project.task'].create({
            'name': 'Test Event Task',
            'project_id': self.test_project.id,
            'user_ids': [(4, self.portal_tp_user.id)],
            'date_start': datetime.now() + timedelta(days=1),
            'date_end': datetime.now() + timedelta(days=1, hours=2),
        })

    def test_01_portal_tp_can_read_task_fields(self):
        """Test that portal treatment professionals can read all required task fields"""
        task_as_portal_tp = self.test_task.sudo(self.portal_tp_user)
        
        # Test core fields
        self.assertTrue(task_as_portal_tp.name)
        self.assertTrue(task_as_portal_tp.project_id)
        self.assertTrue(task_as_portal_tp.user_ids)
        
        # Test custom event fields
        self.assertTrue(task_as_portal_tp.date_start)
        self.assertTrue(task_as_portal_tp.date_end)
        
        # Test overridden fields
        self.assertIsNotNone(task_as_portal_tp.date_start)
        self.assertIsNotNone(task_as_portal_tp.date_end)

    def test_02_portal_tp_can_write_task_fields(self):
        """Test that portal treatment professionals can write to task fields"""
        task_as_portal_tp = self.test_task.sudo(self.portal_tp_user)
        
        # Test writing to various fields
        task_as_portal_tp.write({
            'name': 'Updated Event Name',
            'description': 'Updated description',
            'priority': '1',
            'date_start': datetime.now() + timedelta(days=2),
            'date_end': datetime.now() + timedelta(days=2, hours=3),
        })
        
        self.assertEqual(task_as_portal_tp.name, 'Updated Event Name')
        self.assertEqual(task_as_portal_tp.priority, '1')

    def test_03_portal_tp_can_create_tasks(self):
        """Test that portal treatment professionals can create tasks"""
        task_as_portal_tp = self.env['project.task'].sudo(self.portal_tp_user)
        
        new_task = task_as_portal_tp.create({
            'name': 'New Portal Created Task',
            'project_id': self.test_project.id,
            'date_start': datetime.now() + timedelta(days=3),
            'date_end': datetime.now() + timedelta(days=3, hours=1),
        })
        
        self.assertTrue(new_task.exists())
        self.assertEqual(new_task.name, 'New Portal Created Task')

    def test_04_regular_portal_user_cannot_access_tasks(self):
        """Test that regular portal users cannot access project tasks"""
        task_as_regular_portal = self.test_task.sudo(self.regular_portal_user)
        
        # Should not be able to read task fields
        with self.assertRaises(AccessError):
            _ = task_as_regular_portal.name

    def test_05_portal_task_access_method(self):
        """Test the custom portal task access checking method"""
        # Test with portal TP user (should have access)
        task_as_portal_tp = self.test_task.sudo(self.portal_tp_user)
        self.assertTrue(task_as_portal_tp.check_portal_task_access())
        
        # Test with regular portal user (should not have access)
        task_as_regular_portal = self.test_task.sudo(self.regular_portal_user)
        self.assertFalse(task_as_regular_portal.check_portal_task_access())

    def test_06_project_access_for_portal_tp(self):
        """Test that portal treatment professionals can access projects"""
        project_as_portal_tp = self.test_project.sudo(self.portal_tp_user)
        
        # Should be able to read project fields
        self.assertTrue(project_as_portal_tp.name)
        self.assertTrue(project_as_portal_tp.privacy_visibility)
        self.assertTrue(project_as_portal_tp.is_sports_clinic_project)

    def test_07_record_rule_filtering(self):
        """Test that record rules properly filter accessible tasks"""
        # Create a task that portal TP should NOT have access to
        other_project = self.env['project.project'].create({
            'name': 'Private Project',
            'privacy_visibility': 'employees',  # Not portal accessible
        })
        
        private_task = self.env['project.task'].create({
            'name': 'Private Task',
            'project_id': other_project.id,
        })
        
        # Portal TP should not be able to access this task
        task_as_portal_tp = private_task.sudo(self.portal_tp_user)
        self.assertFalse(task_as_portal_tp.check_portal_task_access())

    def test_08_field_groups_configuration(self):
        """Test that field groups are properly configured"""
        task_model = self.env['project.task']
        
        # Check that critical fields have portal groups
        critical_fields = ['name', 'description', 'user_ids', 'project_id', 'date_start', 'date_end']
        
        for field_name in critical_fields:
            field_obj = task_model._fields.get(field_name)
            self.assertIsNotNone(field_obj, f"Field {field_name} not found")
            
            if hasattr(field_obj, 'groups') and field_obj.groups:
                self.assertIn('bemade_sports_clinic.group_portal_treatment_professional', 
                             field_obj.groups, 
                             f"Field {field_name} missing portal TP group access")

    def test_09_project_creation_helper(self):
        """Test the project creation helper method"""
        # Test creating a sports clinic project
        new_project = self.env['project.project'].create_sports_clinic_project(
            name='Test Helper Project',
            description='Created via helper method'
        )
        
        self.assertTrue(new_project.exists())
        self.assertTrue(new_project.is_sports_clinic_project)
        self.assertEqual(new_project.privacy_visibility, 'portal')
        
        # Check that treatment professionals are followers
        portal_group = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        tp_partners = portal_group.users.mapped('partner_id')
        
        for partner in tp_partners:
            self.assertIn(partner, new_project.message_partner_ids)

    def test_10_default_project_creation(self):
        """Test the default project creation method"""
        default_project = self.env['project.project'].get_or_create_default_sports_project()
        
        self.assertTrue(default_project.exists())
        self.assertEqual(default_project.name, 'Sports Clinic Events')
        self.assertTrue(default_project.is_sports_clinic_project)
        self.assertEqual(default_project.privacy_visibility, 'portal')
