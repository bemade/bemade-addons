# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)


class ProjectTaskSecurityTest(models.TransientModel):
    _name = 'project.task.security.test'
    _description = 'Project Task Security Testing Utility'

    task_id = fields.Many2one('project.task', string='Task to Test', required=True)
    user_id = fields.Many2one('res.users', string='User to Test', required=True)
    test_results = fields.Text(string='Test Results', readonly=True)

    def action_test_field_access(self):
        """Test field access for the specified user and task"""
        self.ensure_one()
        
        # List of critical fields to test
        fields_to_test = [
            'name', 'description', 'user_ids', 'project_id', 'stage_id', 
            'tag_ids', 'partner_id', 'date_deadline', 'priority', 'sequence',
            'state', 'is_closed', 'date_start', 'date_end', 
            'date_event_start', 'date_event_end'
        ]
        
        results = []
        results.append(f"Testing field access for user: {self.user_id.name}")
        results.append(f"Testing task: {self.task_id.name}")
        results.append(f"User groups: {', '.join(self.user_id.groups_id.mapped('name'))}")
        results.append("=" * 50)
        
        # Test as the specified user
        task_as_user = self.task_id.sudo(self.user_id)
        
        for field_name in fields_to_test:
            try:
                # Attempt to read the field
                field_value = getattr(task_as_user, field_name)
                results.append(f"✅ {field_name}: ACCESSIBLE")
                
                # Test field groups if defined
                field_obj = self.env['project.task']._fields.get(field_name)
                if field_obj and hasattr(field_obj, 'groups') and field_obj.groups:
                    results.append(f"   Groups: {field_obj.groups}")
                    
            except AccessError as e:
                results.append(f"❌ {field_name}: ACCESS DENIED - {str(e)}")
            except Exception as e:
                results.append(f"⚠️  {field_name}: ERROR - {str(e)}")
        
        results.append("=" * 50)
        
        # Test model-level access
        try:
            task_as_user.check_access_rights('read')
            results.append("✅ Model READ access: GRANTED")
        except AccessError:
            results.append("❌ Model READ access: DENIED")
            
        try:
            task_as_user.check_access_rights('write')
            results.append("✅ Model WRITE access: GRANTED")
        except AccessError:
            results.append("❌ Model WRITE access: DENIED")
            
        try:
            task_as_user.check_access_rights('create')
            results.append("✅ Model CREATE access: GRANTED")
        except AccessError:
            results.append("❌ Model CREATE access: DENIED")
        
        # Test record-level access
        try:
            task_as_user.check_access_rule('read')
            results.append("✅ Record READ access: GRANTED")
        except AccessError:
            results.append("❌ Record READ access: DENIED")
            
        try:
            task_as_user.check_access_rule('write')
            results.append("✅ Record WRITE access: GRANTED")
        except AccessError:
            results.append("❌ Record WRITE access: DENIED")
        
        # Test portal-specific access method
        if hasattr(task_as_user, 'check_portal_task_access'):
            try:
                portal_access = task_as_user.check_portal_task_access()
                results.append(f"✅ Portal task access: {'GRANTED' if portal_access else 'DENIED'}")
            except Exception as e:
                results.append(f"⚠️  Portal task access: ERROR - {str(e)}")
        
        self.test_results = '\n'.join(results)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task.security.test',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def quick_test_portal_access(self, task_id=None, user_login=None):
        """Quick test method for debugging - can be called from shell"""
        if not task_id:
            # Find any task
            task = self.env['project.task'].search([], limit=1)
            if not task:
                return "No tasks found to test"
            task_id = task.id
            
        if not user_login:
            # Find a portal treatment professional
            portal_group = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
            portal_users = portal_group.users
            if not portal_users:
                return "No portal treatment professionals found"
            user_login = portal_users[0].login
            
        user = self.env['res.users'].search([('login', '=', user_login)], limit=1)
        if not user:
            return f"User {user_login} not found"
            
        # Create test record and run test
        test_record = self.create({
            'task_id': task_id,
            'user_id': user.id
        })
        
        test_record.action_test_field_access()
        return test_record.test_results
