from odoo import models, fields, api, _, Command
import logging

_logger = logging.getLogger(__name__)


class User(models.Model):
    _inherit = "res.users"

    accessible_team_ids = fields.Many2many(
        comodel_name="sports.team",
        compute="_compute_accessible_team_ids",
        inverse="_inverse_accessible_team_ids",
    )

    def _compute_accessible_team_ids(self):
        for rec in self:
            rec.accessible_team_ids = rec.partner_id.teams_served_ids

    def _inverse_accessible_team_ids(self):
        for rec in self:
            removed_teams = rec.partner_id.teams_served_ids - rec.accessible_team_ids
            added_teams = rec.accessible_team_ids - rec.partner_id.teams_served_ids
            removed_teams = rec.partner_id.teams_served_ids.filtered(
                lambda team: team in removed_teams
            )
            removed_teams.remove_access(self)
            self.env["sports.team.staff"].create(
                [
                    {
                        "team_id": team.id,
                        "partner_id": rec.partner_id.id,
                        "role": "other",
                    }
                    for team in added_teams
                ]
            )
    
    def write(self, vals):
        """Override write to trigger treatment professional group assignment when portal access is granted."""
        # Process user updates for portal access changes
        
        # Check if groups_id is being modified (portal access being granted/revoked)
        if 'group_ids' in vals:
            # Get the portal group reference
            portal_group = self.env.ref('base.group_portal')
            
            # Store old group memberships before making changes
            old_groups_by_user = {user.id: user.group_ids.ids for user in self}
            # Store old group memberships for comparison
            
            # Apply the changes first
            result = super().write(vals)
            
            # Check each user to see if portal access was granted
            for user in self:
                old_groups = old_groups_by_user[user.id]
                new_groups = user.group_ids.ids
                # Check if portal access was granted
                
                if portal_group.id in new_groups and portal_group.id not in old_groups:
                    # Portal access was just granted - trigger treatment professional group assignment
                    # Portal access was just granted - trigger treatment professional group assignment
                    staff_records = self.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ])
                    if staff_records:
                        staff_records._update_treatment_professional_group(user)
            
            return result
        else:
            # No group changes, use normal write
            pass
        
        # If groups_id is not being modified, use normal write
        return super().write(vals)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger treatment professional group assignment when portal users are created."""
        # Process user creation for portal access
        
        # Create the users first
        users = super().create(vals_list)
        
        # Get the portal group reference
        portal_group = self.env.ref('base.group_portal')
        # Check for portal access in created users
        
        # Check each created user to see if they were created with portal access
        for user in users:
            # Check if user was created with portal access
            
            if portal_group.id in user.group_ids.ids:
                # User was created with portal access - trigger treatment professional group assignment
                # User was created with portal access - trigger treatment professional group assignment
                staff_records = self.env['sports.team.staff'].search([
                    ('partner_id', '=', user.partner_id.id)
                ])
                if staff_records:
                    staff_records._update_treatment_professional_group(user)
        
        return users
