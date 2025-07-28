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
        _logger.info(f"DEBUG: res.users.write() called with vals: {vals}")
        _logger.info(f"DEBUG: Processing {len(self)} users: {[u.login for u in self]}")
        
        # Check if groups_id is being modified (portal access being granted/revoked)
        if 'groups_id' in vals:
            _logger.info(f"DEBUG: groups_id is being modified: {vals['groups_id']}")
            # Get the portal group reference
            portal_group = self.env.ref('base.group_portal')
            _logger.info(f"DEBUG: Portal group ID: {portal_group.id}")
            
            # Store old group memberships before making changes
            old_groups_by_user = {user.id: user.groups_id.ids for user in self}
            _logger.info(f"DEBUG: Old groups by user: {old_groups_by_user}")
            
            # Apply the changes first
            result = super().write(vals)
            
            # Check each user to see if portal access was granted
            for user in self:
                old_groups = old_groups_by_user[user.id]
                new_groups = user.groups_id.ids
                _logger.info(f"DEBUG: User {user.login} - Old groups: {old_groups}, New groups: {new_groups}")
                
                if portal_group.id in new_groups and portal_group.id not in old_groups:
                    _logger.info(f"DEBUG: Portal access granted to {user.login} - triggering group assignment")
                    # Portal access was just granted - trigger treatment professional group assignment
                    staff_records = self.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ])
                    _logger.info(f"DEBUG: Found {len(staff_records)} staff records for user {user.login}")
                    if staff_records:
                        _logger.info(f"DEBUG: Staff roles: {[(s.team_id.name, s.role) for s in staff_records]}")
                        staff_records._update_treatment_professional_group(user)
                        _logger.info(f"DEBUG: Group assignment completed for {user.login}")
            
            return result
        else:
            _logger.info(f"DEBUG: groups_id not in vals, using normal write")
        
        # If groups_id is not being modified, use normal write
        return super().write(vals)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger treatment professional group assignment when portal users are created."""
        _logger.info(f"DEBUG: res.users.create() called with vals_list: {vals_list}")
        
        # Create the users first
        users = super().create(vals_list)
        
        # Get the portal group reference
        portal_group = self.env.ref('base.group_portal')
        _logger.info(f"DEBUG: Portal group ID: {portal_group.id}")
        
        # Check each created user to see if they were created with portal access
        for user in users:
            _logger.info(f"DEBUG: Created user {user.login} with groups: {user.groups_id.ids}")
            
            if portal_group.id in user.groups_id.ids:
                _logger.info(f"DEBUG: User {user.login} created with portal access - triggering group assignment")
                # User was created with portal access - trigger treatment professional group assignment
                staff_records = self.env['sports.team.staff'].search([
                    ('partner_id', '=', user.partner_id.id)
                ])
                _logger.info(f"DEBUG: Found {len(staff_records)} staff records for user {user.login}")
                if staff_records:
                    _logger.info(f"DEBUG: Staff roles: {[(s.team_id.name, s.role) for s in staff_records]}")
                    staff_records._update_treatment_professional_group(user)
                    _logger.info(f"DEBUG: Group assignment completed for {user.login}")
        
        return users
