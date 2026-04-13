from odoo import api, fields, models
from odoo.exceptions import AccessError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Portal access group definition for reuse - only authorized sports clinic users
    _portal_groups = 'base.group_user,bemade_sports_clinic.group_portal_treatment_professional,bemade_sports_clinic.group_portal_team_coach'

    # Override core fields to grant portal access
    name = fields.Char(groups=_portal_groups)
    description = fields.Html(groups=_portal_groups)
    user_ids = fields.Many2many(groups=_portal_groups)
    project_id = fields.Many2one(groups=_portal_groups)
    stage_id = fields.Many2one(groups=_portal_groups)
    tag_ids = fields.Many2many(groups=_portal_groups)
    partner_id = fields.Many2one(groups=_portal_groups)
    date_deadline = fields.Datetime(groups=_portal_groups)
    priority = fields.Selection(groups=_portal_groups)
    sequence = fields.Integer(groups=_portal_groups)
    state = fields.Selection(groups=_portal_groups)
    is_closed = fields.Boolean(groups=_portal_groups)
    task_properties = fields.Properties(groups=_portal_groups)
    
    date_start = fields.Datetime(
        string='Starting Date',
        groups=_portal_groups
    )
    
    date_end = fields.Datetime(
        string='Ending Date', 
        groups=_portal_groups
    )



    @api.model
    def check_portal_access_rights(self, operation, raise_exception=True):
        """Check if portal treatment professional has access to perform operation"""
        if self.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional'):
            allowed_operations = ['read', 'write', 'create']
            if operation in allowed_operations:
                return True
        
        if raise_exception:
            raise AccessError(f"Portal treatment professionals cannot perform {operation} operation")
        return False

    def check_portal_task_access(self):
        """Check if current user can access this specific task"""
        if not self.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional'):
            return False
            
        user = self.env.user
        partner = user.partner_id
        
        # Check if user is assigned to task
        if user in self.user_ids:
            return True
            
        # Check if user is follower of task
        if partner in self.message_partner_ids:
            return True
            
        # Check if user is follower of project
        if self.project_id and partner in self.project_id.message_partner_ids:
            return True
            
        # Check if user's teams are partners of the project
        if self.project_id:
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            if self.project_id.partner_id.id in team_ids:
                return True
            
        return False
