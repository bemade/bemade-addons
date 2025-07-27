from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class TeamManagementPortal(CustomerPortal):
    
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        return values

    def _check_team_access(self, team_id, check_staff=False):
        """Verify the current user has access to this team.
        
        :param int team_id: ID of the team to check access for
        :param bool check_staff: If True, only allow team staff members
        :return: The team record if access is granted
        :raises: MissingError if team not found
        :raises: AccessError if user doesn't have permission
        """
        team = request.env['sports.team'].browse(int(team_id))
        if not team:
            raise MissingError(_("Team not found"))
            
        user = request.env.user
        
        # Check if user is a staff member of this team
        is_team_staff = team.staff_ids.filtered(
            lambda s: user.partner_id in s.user_ids.partner_id
        )
        
        # Check if user is a treatment professional with access
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_professional = request.env.user.has_group(
            'bemade_sports_clinic.group_portal_treatment_professional'
        )
        
        if check_staff and not is_team_staff:
            # Only team staff can perform certain actions
            raise AccessError(_("Only team staff members can perform this action."))
            
        if not (is_team_staff or is_treatment_professional):
            raise AccessError(_("You don't have permission to access this team."))
            
        return team
        
    def _check_team_staff_access(self, team):
        """Check if the current user is a staff member of the team"""
        user = request.env.user
        return team.staff_ids.filtered(
            lambda s: user.partner_id in s.user_ids.partner_id
        )
        
    def _check_treatment_professional_access(self):
        """Check if the current user is a treatment professional"""
        return request.env.user.has_group(
            'bemade_sports_clinic.group_portal_treatment_professional'
        ) or request.env.user.has_group('base.group_system')

    @http.route(['/my/team/<int:team_id>/player/<int:player_id>/request_removal'],
                type='http', auth="user", website=True, methods=['POST'])
    def portal_request_player_removal(self, team_id, player_id, **post):
        """
        Request removal of a player from the team.
        This is used by coaches to request removal, which creates a task for the head therapist.
        """
        try:
            team = self._check_team_access(team_id, check_staff=True)
            patient = request.env['sports.patient'].browse(int(player_id))
            
            if not patient.exists():
                raise MissingError(_("Player not found"))
                
            if team not in patient.team_ids:
                raise ValidationError(_("Player is not a member of this team"))
                
            # Check if there's already a pending removal
            if patient.pending_removal:
                raise ValidationError(_("A removal request is already pending for this player"))
                
            # Get and validate reason
            reason = (post.get('reason') or '').strip()
            if not reason:
                raise ValidationError(_("Please provide a reason for the removal request"))
                
            # Request removal (this will handle the activity creation and logging)
            # No sudo() needed as proper permission checks are in request_team_removal
            patient._request_team_removal(team.id, reason=reason)
            
            # Store success message in session for display after redirect
            request.session['notification'] = {
                'type': 'success',
                'title': _('Removal Request Submitted'),
                'message': _('Your request to remove %s from the team has been submitted for review.') % patient.name,
                'sticky': False,
            }
            
            return request.redirect(f"/my/team/{team_id}")
            
        except Exception as e:
            _logger.error("Error requesting player removal: %s", str(e), exc_info=True)
            error_message = _("Error requesting removal: %s") % str(e)
            return request.redirect(f"/my/team/{team_id}?error={error_message}".replace(' ', '+'))
    
    @http.route(['/my/team/<int:team_id>/player/<int:player_id>/remove'],
               type='http', auth="user", website=True, methods=['POST'])
    def portal_remove_player(self, team_id, player_id, **post):
        """
        Directly remove a player from the team.
        Only accessible by treatment professionals or team staff.
        """
        try:
            team = self._check_team_access(team_id)
            
            # Only treatment professionals or team staff can directly remove
            if not (self._check_treatment_professional_access() or self._check_team_staff_access(team)):
                raise AccessError(_("You don't have permission to remove players from this team."))
                
            patient = request.env['sports.patient'].browse(int(player_id))
            if not patient.exists():
                raise MissingError(_("Player not found"))
                
            if team not in patient.team_ids:
                raise ValidationError(_("Player is not a member of this team"))
                
            # Check if this is a pending removal that's being approved
            is_approving_pending = patient.pending_removal and self._check_treatment_professional_access()
                
            # Process removal with the appropriate action - no sudo needed as remove_from_team has built-in permission checks
            result = patient._remove_from_team(team.id, clear_pending=True)
            
            # Store success message in session for display after redirect
            request.session['notification'] = {
                'type': 'success',
                'title': _('Player Removed'),
                'message': _('%s has been successfully removed from the team.') % patient.name,
                'sticky': False,
            }
            
            return request.redirect(f"/my/team/{team_id}")
            
        except Exception as e:
            _logger.error("Error removing player: %s", str(e), exc_info=True)
            error_message = _("Error removing player: %s") % str(e)
            return request.redirect(f"/my/team/{team_id}?error={error_message}".replace(' ', '+'))
    
    @http.route(['/my/team/<int:team_id>/add_player'],
                type='http', auth="user", website=True)
    def portal_add_player_form(self, team_id, **kw):
        """Display the form to add a new player to a team."""
        try:
            team = self._check_team_access(team_id)
            values = self._prepare_portal_layout_values()
            
            # Check for success/error messages
            success = request.httprequest.args.get('success')
            if success == 'player_reactivated':
                values['success'] = _("An archived player was found and reactivated, and has been added to this team.")
            elif success == 'player_added_to_team':
                values['success'] = _("An existing player was found and has been added to this team.")
            elif success == 'player_created':
                values['success'] = _("A new player has been created and added to the team.")
            
            values.update({
                'team': team,
                'page_name': 'add_player',
                'error': request.httprequest.args.get('error'),
            })
            
            # Preserve form data if there was an error
            if kw.get('error'):
                values.update({
                    'first_name': kw.get('first_name', ''),
                    'last_name': kw.get('last_name', ''),
                    'email': kw.get('email', ''),
                    'phone': kw.get('phone', ''),
                    'date_of_birth': kw.get('date_of_birth', ''),
                })
                
            return request.render("bemade_sports_clinic.portal_add_player", values)
            
        except (AccessError, MissingError) as e:
            return request.redirect('/my')
        except Exception as e:
            _logger.exception("Error in portal_add_player_form")
            values = request.params.copy()
            values['error'] = _("An error occurred while loading the form. Please try again.")
            return request.render("bemade_sports_clinic.portal_add_player", values)

    @http.route(['/my/team', '/my/team/<int:team_id>'], type='http', auth="user", website=True)
    def portal_team_players(self, team_id=None, **kw):
        """Display the list of players for a team."""
        try:
            if not team_id:
                # If no team_id is provided, try to get it from the query string
                team_id = request.httprequest.args.get('team_id')
                if not team_id:
                    # If still no team_id, redirect to the teams list
                    return request.redirect('/my/teams')
                
            team = self._check_team_access(team_id)
            
            # Get all players for the team
            players = request.env['sports.patient'].search([
                ('team_ids', 'in', [team.id]),
                ('active', '=', True)
            ], order='last_name, first_name')
            
            # Check user permissions for UI elements
            is_treatment_prof = request.env.user.has_group(
                'bemade_sports_clinic.group_portal_treatment_professional')
            is_admin = request.env.user.has_group('base.group_system')
            is_team_staff = team.staff_ids.filtered(
                lambda s: request.env.user.partner_id in s.user_ids.partner_id
            )
            
            values = {
                'page_name': 'team_players',
                'team': team,
                'players': players,
                'default_url': f'/my/team/{team.id}',
                'user_has_group': request.env.user.has_group,  # Pass the has_group method to template
                'user': request.env.user,
                'is_treatment_prof': is_treatment_prof or is_admin,
                'is_team_staff': bool(is_team_staff),
            }
            
            # Add success/error messages if present in the URL
            success = request.httprequest.args.get('success')
            error = request.httprequest.args.get('error')
            
            if success == 'player_removed':
                values['success'] = _("Player has been successfully removed from the team.")
            elif success == 'removal_requested':
                values['success'] = _("A request to remove this player has been submitted to the head therapist.")
            elif success == 'player_reactivated':
                values['success'] = _("An archived player was found and reactivated, and has been added to this team.")
            elif success == 'player_added_to_team':
                values['success'] = _("Player has been added to the team.")
                
            if error:
                values['error'] = error
            
            return request.render('bemade_sports_clinic.portal_my_team_players', values)
            
        except (AccessError, MissingError) as e:
            return request.redirect('/my/teams?error=%s' % str(e))

    def _find_existing_patient(self, first_name, last_name, email=None, phone=None):
        """Search for an existing patient by name and contact information."""
        domain = [
            ('first_name', '=ilike', first_name.strip()),
            ('last_name', '=ilike', last_name.strip()),
            '|',
            ('active', '=', True),
            ('active', '=', False),  # Include inactive to handle archived players
        ]
        
        # Additional search criteria if email or phone is provided
        if email and email.strip():
            domain = ['|'] + domain + [
                '&',
                ('partner_id.email', '=ilike', email.strip()),
                ('partner_id.email', '!=', False)
            ]
        if phone and phone.strip():
            domain = ['|'] + domain + [
                '&',
                ('partner_id.phone', '=', phone.strip()),
                ('partner_id.phone', '!=', False)
            ]
        
        # Search active records first (portal users always have access to active records)
        active_patient = request.env['sports.patient'].search(domain + [('active', '=', True)], limit=1)
        if active_patient:
            return active_patient
            
        # If no active patient found, check if user has permission to see inactive records
        # Only treatment professionals or admins should see inactive/archived patients
        # Use request.env.user.has_group() directly to avoid security violations
        if request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
           request.env.user.has_group('base.group_system'):
            return request.env['sports.patient'].search(domain + [('active', '=', False)], limit=1)
            
        return request.env['sports.patient'].browse([])  # Empty recordset if no matches

    @http.route(['/my/team/<int:team_id>/add_player/submit'],
                type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_add_player_submit(self, team_id, **post):
        """Handle the form submission to add a new player."""
        try:
            team = self._check_team_access(team_id)
            
            # Basic validation
            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            email = (post.get('email') or '').strip()
            phone = (post.get('phone') or '').strip()
            
            if not first_name or not last_name:
                raise UserError(_("First name and last name are required"))
            
            # Check for existing player
            existing_patient = self._find_existing_patient(
                first_name, last_name, email, phone
            )
            
            if existing_patient:
                # Determine the action taken for logging and messaging
                action_taken = []
                
                # Reactivate if archived
                if not existing_patient.active:
                    existing_patient.write({'active': True})
                    action_taken.append("reactivated")
                    _logger.info(
                        "Reactivated archived player %s for team %s by user %s",
                        existing_patient.name, team.name, request.env.user.name
                    )
                
                # Add to team if not already a member
                if team not in existing_patient.team_ids:
                    existing_patient.write({
                        'team_ids': [(4, team.id)],
                    })
                    action_taken.append("added to team")
                    _logger.info(
                        "Added existing player %s to team %s by user %s",
                        existing_patient.name, team.name, request.env.user.name
                    )
                
                # Determine the appropriate success message
                if "reactivated" in action_taken:
                    success_param = "player_reactivated"
                else:
                    success_param = "player_added_to_team"
                
                # Redirect to team page with appropriate message
                return request.redirect(
                    f"/my/team?team_id={team.id}&success={success_param}"
                )
            
            # No existing player found, create a new one
            patient_vals = {
                'first_name': first_name,
                'last_name': last_name,
                'team_ids': [(4, team.id)],
                'email': email or False,
                'phone': phone or False,
            }
            
            if post.get('date_of_birth'):
                patient_vals['date_of_birth'] = post.get('date_of_birth')
            
            # Create patient through the portal_create_patient method which has proper access controls
            patient = request.env['sports.patient'].create_portal_patient(patient_vals)
            
            # Log the action
            _logger.info(
                "Created new player %s and added to team %s by user %s",
                patient.name, team.name, request.env.user.name
            )
            
            # Redirect to team page with success message
            return request.redirect(
                f"/my/team?team_id={team.id}&success=player_created"
            )
            
        except UserError as e:
            values = {
                'error': str(e),
                'team': team,
                'page_name': 'add_player',
            }
            values.update(post)
            return request.render("bemade_sports_clinic.portal_add_player", values)
            
        except (AccessError, MissingError) as e:
            return request.redirect('/my')
            
        except Exception as e:
            _logger.exception("Error in portal_add_player_submit")
            values = {
                'error': _("An error occurred while adding the player. Please try again later."),
                'team': team,
                'page_name': 'add_player',
            }
            values.update(post)
            return request.render("bemade_sports_clinic.portal_add_player", values)
