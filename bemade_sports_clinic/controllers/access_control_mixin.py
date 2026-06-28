#
#    Bemade Inc.
#
#    Copyright (C) October 2023 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the Odoo Proprietary License v1.0 (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#    or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#

from odoo import http, _, fields
from odoo.exceptions import UserError, AccessError, MissingError
from odoo.http import request
from datetime import datetime
import pytz


class AccessControlMixin:
    """
    Mixin class providing common access control methods for portal controllers.
    
    This centralizes access control logic to avoid duplication across multiple controllers
    and ensures consistent security checks throughout the portal interface.
    """

    # ------------------------------------------------------------------
    # Shared portal helpers (consolidated here after the dead-route audit;
    # previously duplicated across events_portal / team_staff_portal /
    # timesheets_portal where only one copy won by import order).
    # ------------------------------------------------------------------

    def _parse_portal_datetime(self, val):
        """Parse a datetime-local input (YYYY-MM-DDTHH:MM[:SS]) from the portal
        as user-local time and convert to a UTC string for fields.Datetime.
        Returns False if empty; returns the raw value if it can't be parsed.
        """
        if not val:
            return False
        dt = None
        try:
            if 'T' in val:
                try:
                    dt = datetime.strptime(val, '%Y-%m-%dT%H:%M')
                except ValueError:
                    dt = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S')
            else:
                try:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M')
                except ValueError:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Fallback: let the ORM try to coerce whatever string was provided.
            return val

        user_tz = http.request.env.tz
        local_dt = user_tz.localize(dt)
        utc_dt = local_dt.astimezone(pytz.UTC)
        return fields.Datetime.to_string(utc_dt)

    def _prepare_events_domain(self, view_type='all', include_cancelled=False):
        """Prepare domain for sports events based on user access.

        Cancelled events are excluded by default so the portal list and
        calendar mirror the internal views (task 1235). Callers pass
        include_cancelled=True (driven by an explicit ``show_cancelled``
        toggle) to surface them again.
        """
        user = http.request.env.user
        partner = user.partner_id

        # Therapists see all events; coaches only their teams' events.
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
            user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')

        if is_therapist:
            base_domain = []
        elif is_coach:
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            base_domain = [('team_ids', 'in', team_ids or [0])]
        else:
            base_domain = [('id', '=', 0)]  # No results

        # View-specific filters
        if view_type == 'my':
            base_domain.append(('assigned_staff_ids', 'in', [user.id]))
        elif view_type == 'unassigned':
            base_domain.append(('assigned_staff_ids', '=', False))
        elif view_type == 'missing_timesheets':
            shared_users = http.request.env['res.users'].search([('partner_id', '=', partner.id)])
            shared_user_ids = shared_users.ids or [user.id]
            base_domain.extend([
                ('assigned_staff_ids', 'in', shared_user_ids),
                '!',
                ('timesheet_ids.user_id', 'in', shared_user_ids),
            ])
        # 'all' view uses base domain only

        # Drop cancelled events from the default surfaces unless explicitly
        # requested. Appended last; the implicit-AND combine is correct even
        # for the missing_timesheets branch (which uses a '!' prefix operator).
        if not include_cancelled:
            base_domain.append(('state', '!=', 'cancelled'))
        return base_domain

    def _get_accessible_teams(self):
        """Teams accessible to the current user (therapists: all; coaches: staffed)."""
        user = http.request.env.user
        partner = user.partner_id
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
            user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if is_therapist:
            teams = http.request.env['sports.team'].search([])
        else:
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            teams = http.request.env['sports.team'].browse(team_ids)
        return teams.sorted('name')

    def _get_organizations(self):
        """Organizations (parent partners) of the accessible teams."""
        teams = self._get_accessible_teams()
        organizations = teams.mapped('parent_id').filtered(lambda p: p)
        return organizations.sorted('name')

    # ------------------------------------------------------------------
    # Post/Redirect/Get helpers for form-validation errors.
    # On a validation failure a submit handler stashes the message (and the
    # submitted fields) in the session and redirects (GET) back to the form;
    # the form's GET handler calls _portal_pop_flash() to render them. This
    # avoids re-POST-on-refresh and the fragile "re-render the form template
    # inline" pattern (which repeatedly 500'd on missing template context).
    # ------------------------------------------------------------------

    def _portal_flash(self, error, form_data=None):
        """Stash a validation error + submitted form data for a PRG redirect."""
        request.session['portal_flash_error'] = error
        request.session['portal_flash_data'] = dict(form_data or {})

    def _portal_pop_flash(self):
        """Return (error, form_data) stashed by _portal_flash, clearing them.

        form_data is a plain dict of the user's previous input, for re-prefill.
        """
        return (
            request.session.pop('portal_flash_error', None),
            request.session.pop('portal_flash_data', {}) or {},
        )

    def _check_team_access(self, team_id, check_staff=False):
        """
        Verify the current user has access to this team.
        
        :param int team_id: ID of the team to check access for
        :param bool check_staff: If True, only allow team staff members
        :return: The team record if access is granted
        :raises: MissingError if team not found
        :raises: AccessError if user doesn't have permission
        """
        team = request.env['sports.team'].browse(int(team_id))
        if not team.exists():
            raise MissingError(_("Team not found"))
            
        user = request.env.user
        
        # Check if user is a staff member of this team
        is_team_staff = team.staff_ids.filtered(
            lambda s: user.partner_id in s.user_ids.partner_id
        )
        
        # Check if user is a treatment professional with access
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
        """
        Check if the current user is a staff member of the team.
        
        :param team: Team record to check staff access for
        :return: Staff records if user is team staff, empty recordset otherwise
        """
        user = request.env.user
        return team.staff_ids.filtered(
            lambda s: user.partner_id in s.user_ids.partner_id
        )
    
    def _check_treatment_professional_access(self):
        """
        Check if the current user is a treatment professional.
        
        :return: True if user is a treatment professional or system admin
        """
        return (request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or 
                request.env.user.has_group('base.group_system'))
    
    def _check_access_to_patient(self, patient_id):
        """
        Verify the user has access to this patient.
        
        :param int patient_id: ID of the patient to check access for
        :return: The patient record if access is granted
        :raises: UserError if user doesn't have permission or patient not found
        """
        user = request.env.user
        patient = request.env['sports.patient'].browse(int(patient_id))
        
        if not patient.exists():
            raise MissingError(_('Patient not found.'))

        # Record access is team-gated for EVERYONE, including treatment
        # professionals: a TP may find an unteamed patient in portal search
        # (task 640) to add them to a team, but full patient-record access
        # requires being staff on one of the patient's teams. System admins
        # always pass.
        if user.has_group('base.group_system'):
            return patient

        # Check if user has access through team staff relationships (original task portal logic)
        user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
        patient_teams = patient.team_ids

        # User must be staff on at least one of the patient's teams
        has_team_access = bool(user_teams & patient_teams)

        # Treatment professionals still need to be staff on the patient's teams
        # They don't get blanket access to all patients
        if not has_team_access:
            raise AccessError(_('You do not have access to this patient.'))

        return patient
    
    def _check_access_to_injury(self, injury_id):
        """
        Verify the user has access to this injury.
        
        :param int injury_id: ID of the injury to check access for
        :return: The injury record if access is granted
        :raises: UserError if user doesn't have permission or injury not found
        """
        user = request.env.user
        injury = request.env['sports.patient.injury'].browse(int(injury_id))
        
        if not injury.exists():
            raise MissingError(_('Injury not found.'))

        # Team-gated for everyone (see _check_access_to_patient, task 640).
        # System admins always pass.
        if user.has_group('base.group_system'):
            return injury

        # Check if user has access through team staff relationships (original task portal logic)
        user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
        patient_teams = injury.patient_id.team_ids

        # User must be staff on at least one of the patient's teams
        has_team_access = bool(user_teams & patient_teams)

        # Treatment professionals still need to be staff on the patient's teams
        # They don't get blanket access to all injuries
        if not has_team_access:
            raise AccessError(_('You do not have access to this injury.'))

        return injury

    def _check_access_to_event(self, event_id):
        """Verify the user has access to this event.

        Mirror the access semantics used by the event portal:
        - treatment professionals can access event records
        - coaches must be staff on at least one of the event teams
        - system users always allowed
        """
        user = request.env.user
        event = request.env['sports.event'].browse(int(event_id))

        if not event.exists():
            raise MissingError(_('Event not found.'))

        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
            user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')

        if user.has_group('base.group_system'):
            return event

        if is_therapist:
            return event

        if is_coach:
            user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
            has_team_access = bool(user_teams & event.team_ids)
            if not has_team_access:
                raise AccessError(_('You do not have access to this event.'))
            return event

        raise AccessError(_('You do not have access to this event.'))
    
    def _check_access_to_task_model(self, model_name, record_id):
        """
        Verify the user has access to a task-related model record.
        
        :param str model_name: Name of the model ('sports.patient', 'sports.team', 'sports.patient.injury')
        :param int record_id: ID of the record to check access for
        :return: The record if access is granted
        :raises: UserError if user doesn't have permission or record not found
        """
        valid_models = ['sports.patient', 'sports.patient.injury', 'sports.team', 'sports.event']
        if model_name not in valid_models:
            raise UserError(_('Invalid model specified.'))
        
        if model_name == 'sports.patient':
            return self._check_access_to_patient(record_id)
        elif model_name == 'sports.patient.injury':
            return self._check_access_to_injury(record_id)
        elif model_name == 'sports.team':
            return self._check_team_access(record_id)
        elif model_name == 'sports.event':
            return self._check_access_to_event(record_id)
        
        # This should never be reached due to the valid_models check above
        raise UserError(_('Invalid model specified.'))
