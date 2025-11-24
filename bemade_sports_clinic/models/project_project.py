# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    # Portal access group definition for reuse - only authorized sports clinic users
    _portal_groups = 'base.group_user,bemade_sports_clinic.group_portal_treatment_professional,bemade_sports_clinic.group_portal_team_coach'

    # Override core fields to grant portal access
    name = fields.Char(groups=_portal_groups)
    description = fields.Html(groups=_portal_groups)
    partner_id = fields.Many2one(groups=_portal_groups)
    user_id = fields.Many2one(groups=_portal_groups)
    privacy_visibility = fields.Selection(groups=_portal_groups)
    is_favorite = fields.Boolean(groups=_portal_groups)
    color = fields.Integer(groups=_portal_groups)
    stage_id = fields.Many2one(groups=_portal_groups)
    
    # Sports clinic specific fields
    is_sports_clinic_project = fields.Boolean(
        string='Sports Clinic Project',
        default=False,
        help='Mark this project as related to sports clinic activities',
        groups=_portal_groups
    )
    
    related_team_ids = fields.Many2many(
        'sports.team',
        string='Related Teams',
        help='Teams associated with this project',
        groups=_portal_groups
    )

    @api.model
    def create_sports_clinic_project(self, name, team_id=None, description=None):
        """Create a project specifically for sports clinic events"""
        vals = {
            'name': name,
            'is_sports_clinic_project': True,
            'privacy_visibility': 'portal',  # Allow portal access
            'description': description or f'Project for sports clinic events: {name}',
        }
        
        if team_id:
            vals['partner_id'] = team_id  # Set team as project partner
            
        project = self.create(vals)
        
        # Only add authorized treatment professionals as followers
        if team_id:
            project.ensure_portal_access_for_treatment_professionals()
            
        return project

    def ensure_portal_access_for_treatment_professionals(self):
        """Ensure authorized treatment professionals have access to this project"""
        self.ensure_one()
        
        # Only add treatment professionals who have team relationships with this project
        if self.partner_id:  # Project must have a partner (team)
            # Find treatment professionals who are staff on this team
            team_staff = self.env['sports.team.staff'].search([
                ('team_id', '=', self.partner_id.id),
                ('role', 'in', ['therapist', 'head_therapist'])
            ])
            
            authorized_partners = team_staff.mapped('partner_id')
            current_followers = self.message_partner_ids
            new_followers = authorized_partners - current_followers
            
            if new_followers:
                self.with_context(
                    tracking_disable=True,
                    mail_create_nolog=True,
                    mail_create_nosubscribe=True,
                    mail_auto_subscribe_no_notify=True,
                    mail_notify_force_send=False,
                ).message_subscribe(partner_ids=new_followers.ids)
                
        return True

    @api.model
    def get_or_create_default_sports_project(self):
        """Get or create a default project for sports clinic events"""
        default_project = self.search([
            ('is_sports_clinic_project', '=', True),
            ('name', '=', 'Sports Clinic Events')
        ], limit=1)
        
        if not default_project:
            default_project = self.create_sports_clinic_project(
                name='Sports Clinic Events',
                description='Default project for sports clinic events and activities'
            )
            
        # Ensure portal access is configured
        default_project.ensure_portal_access_for_treatment_professionals()
        
        return default_project
