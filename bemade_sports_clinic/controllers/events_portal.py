from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo import http, _, fields
from odoo.exceptions import UserError, AccessError
from datetime import datetime, timedelta
from .access_control_mixin import AccessControlMixin
import logging

_logger = logging.getLogger(__name__)


class EventsPortal(CustomerPortal, AccessControlMixin):
    
    def _prepare_home_portal_values(self, counters):
        """Add events count to portal home"""
        rtn = super()._prepare_home_portal_values(counters)
        if 'events_count' in counters:
            events_domain = self._prepare_events_domain()
            rtn['events_count'] = http.request.env['sports.event'].search_count(events_domain)
        return rtn

    def _prepare_events_domain(self, view_type='all'):
        """Prepare domain for sports events based on user access"""
        user = http.request.env.user
        partner = user.partner_id
        
        # Check if user is therapist (can see all events) or coach (only their teams)
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        if is_therapist:
            # Therapists can see all events
            base_domain = []
        elif is_coach:
            # Coaches can only see events for teams they are staff on
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            base_domain = [('team_id', 'in', team_ids or [0])]
        else:
            # No access for other users
            base_domain = [('id', '=', 0)]  # No results
        
        # Add view-specific filters
        if view_type == 'my':
            # My Events: assigned to current user
            base_domain.append(('assigned_staff_ids', 'in', [user.id]))
        elif view_type == 'unassigned':
            # Unassigned Events: no assigned staff
            base_domain.append(('assigned_staff_ids', '=', False))
        # 'all' view uses base domain only
        
        return base_domain

    def _get_treatment_professionals(self):
        """Get all treatment professionals from team staff with relevant roles"""
        # Search for users who are on team staff with therapist, head therapist, or doctor roles
        team_staff_users = http.request.env['sports.team.staff'].search([
            ('role', 'in', ['therapist', 'head_therapist', 'doctor', 'treatment_professional'])
        ]).mapped('partner_id.user_ids')
        
        # Filter active users and sort by name
        active_users = team_staff_users.filtered(lambda u: u.active)
        
        _logger.info(f"Found {len(active_users)} treatment professionals from team staff: {[u.name for u in active_users]}")
        return active_users.sorted('name')

    def _get_accessible_teams(self):
        """Get teams accessible to current user"""
        user = http.request.env.user
        partner = user.partner_id
        
        # Check if user is therapist (can see all teams) or coach (only their teams)
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        
        if is_therapist:
            # Therapists can see all teams
            teams = http.request.env['sports.team'].search([])
        else:
            # Coaches can only see teams they are staff on
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            teams = http.request.env['sports.team'].browse(team_ids)
        
        return teams.sorted('name')
    
    def _get_organizations(self):
        """Get organizations (parent partners of teams)"""
        teams = self._get_accessible_teams()
        organizations = teams.mapped('parent_id').filtered(lambda p: p)
        return organizations.sorted('name')

    @http.route(['/my/events', '/my/events/page/<int:page>'], type='http', auth='user', website=True)
    def view_events(self, page=1, view_type='all', team_id=None, organization_id=None, assigned_user_id=None, 
                   date_from=None, date_to=None, sortby=None, search=None, **kw):
        """Main events view with filtering and pagination"""
        
        # Check access
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        if not (is_therapist or is_coach or user.has_group('base.group_system')):
            raise AccessError(_("You don't have access to events."))
        
        # Prepare base domain
        domain = self._prepare_events_domain(view_type)
        
        # Apply additional filters
        if team_id:
            domain.append(('team_id', '=', int(team_id)))
        
        if organization_id:
            org_id = int(organization_id)
            domain.append(('partner_id', '=', org_id))
            # Debug: Log organization filter
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"Organization filter applied: partner_id = {org_id}")
        
        if assigned_user_id:
            domain.append(('assigned_staff_ids', 'in', [int(assigned_user_id)]))
        
        if date_from:
            try:
                date_from_dt = fields.Datetime.from_string(date_from)
                domain.append(('date_start', '>=', date_from_dt))
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_dt = fields.Datetime.from_string(date_to)
                domain.append(('date_start', '<=', date_to_dt))
            except ValueError:
                pass
        
        if search:
            domain.extend([
                '|', '|', '|',
                ('name', 'ilike', search),
                ('description', 'ilike', search),
                ('team_id.name', 'ilike', search),
                ('venue_id.name', 'ilike', search)
            ])
        
        # Sorting options - default to date ascending as requested
        sort_options = {
            'date': 'date_start asc',
            'date_desc': 'date_start desc', 
            'name': 'name',
            'team': 'team_id',
            'assigned': 'assigned_staff_ids',
        }
        order = sort_options.get(sortby, 'date_start asc')  # Default ascending by date
        
        # Debug: Log final domain and count
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"Final events domain: {domain}")
        
        # Count and pagination
        event_count = http.request.env['sports.event'].search_count(domain)
        _logger.info(f"Event count with domain: {event_count}")
        pager_values = pager(
            url='/my/events',
            url_args={'view_type': view_type, 'team_id': team_id, 'organization_id': organization_id,
                     'assigned_user_id': assigned_user_id, 'date_from': date_from,
                     'date_to': date_to, 'sortby': sortby, 'search': search},
            total=event_count,
            page=page,
            step=self._items_per_page,
        )
        
        # Get events
        events = http.request.env['sports.event'].search(
            domain, 
            order=order, 
            limit=self._items_per_page, 
            offset=pager_values['offset']
        )
        
        # Get filter options
        teams = self._get_accessible_teams()
        organizations = self._get_organizations()
        treatment_professionals = self._get_treatment_professionals()
        
        # Debug: Log filter options
        _logger.info(f"Available organizations: {[(org.id, org.name) for org in organizations]}")
        _logger.info(f"Received organization_id parameter: {organization_id}")
        
        # Debug: Check sample events and their partner_id values
        sample_events = http.request.env['sports.event'].search([], limit=5)
        for event in sample_events:
            _logger.info(f"Event '{event.name}': team={event.team_id.name if event.team_id else None}, partner_id={event.partner_id.name if event.partner_id else None}")
        
        # Check if user can edit events (only therapists)
        can_edit = is_therapist
        
        values = {
            'events': events,
            'page_name': 'events',
            'pager': pager_values,
            'default_url': '/my/events',
            'view_type': view_type,
            'team_id': int(team_id) if team_id else None,
            'organization_id': int(organization_id) if organization_id else None,
            'assigned_user_id': int(assigned_user_id) if assigned_user_id else None,
            'date_from': date_from,
            'date_to': date_to,
            'sortby': sortby,
            'search': search,
            'teams': teams,
            'organizations': organizations,
            'treatment_professionals': treatment_professionals,
            'can_edit': can_edit,
        }
        
        return http.request.render('bemade_sports_clinic.portal_events_list', values)

    @http.route(['/my/event/<int:event_id>'], type='http', auth='user', website=True)
    def view_event_detail(self, event_id, **kw):
        """View individual event detail"""
        
        # Check access
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        if not (is_therapist or is_coach or user.has_group('base.group_system')):
            raise AccessError(_("You don't have access to events."))
        
        # Get the event
        event = http.request.env['sports.event'].browse(event_id)
        if not event.exists():
            return http.request.not_found()
        
        # Check team access for coaches
        if is_coach and not is_therapist:
            partner = user.partner_id
            team_staff_rels = partner.team_staff_rel_ids
            accessible_team_ids = team_staff_rels.mapped('team_id.id')
            if event.team_id.id not in accessible_team_ids:
                raise AccessError(_("You don't have access to this event."))
        
        # Check if user can edit (only therapists)
        can_edit = is_therapist
        
        values = {
            'event': event,
            'page_name': 'event_detail',
            'can_edit': can_edit,
        }
        
        return http.request.render('bemade_sports_clinic.portal_event_detail', values)

    @http.route(['/my/event/<int:event_id>/edit'], type='http', auth='user', website=True)
    def edit_event_form(self, event_id, **kw):
        """Edit event form - only accessible to therapists"""
        
        # Check access - only therapists can edit
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to edit events."))
        
        # Get the event
        event = http.request.env['sports.event'].browse(event_id)
        if not event.exists():
            return http.request.not_found()
        
        # Get filter options for form
        teams = http.request.env['sports.team'].search([])
        treatment_professionals = self._get_treatment_professionals()
        venues = http.request.env['res.partner'].search([('is_venue', '=', True)])
        
        values = {
            'event': event,
            'teams': teams,
            'treatment_professionals': treatment_professionals,
            'venues': venues,
            'page_name': 'event_edit',
        }
        
        return http.request.render('bemade_sports_clinic.portal_event_edit', values)

    @http.route(['/my/event/<int:event_id>/save'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def save_event(self, event_id, **post):
        """Save event changes - only accessible to therapists"""
        
        # Debug: Log all POST data
        _logger.info(f"Full POST data received: {dict(post)}")
        _logger.info(f"POST keys: {list(post.keys())}")
        
        # Check access - only therapists can edit
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to edit events."))
        
        # Get the event
        event = http.request.env['sports.event'].browse(event_id)
        if not event.exists():
            return http.request.not_found()
        
        try:
            # Update event fields
            update_vals = {}
            
            if 'name' in post:
                update_vals['name'] = post['name']
            if 'description' in post:
                update_vals['description'] = post['description']
            if 'team_id' in post and post['team_id']:
                update_vals['team_id'] = int(post['team_id'])
            if 'venue_id' in post and post['venue_id']:
                update_vals['venue_id'] = int(post['venue_id'])
            if 'event_type' in post:
                update_vals['event_type'] = post['event_type']
            if 'state' in post:
                update_vals['state'] = post['state']
            if 'date_start' in post and post['date_start']:
                # Parse datetime from HTML datetime-local format (ISO format)
                date_str = post['date_start']
                try:
                    if 'T' in date_str:
                        # ISO format: 2025-05-26T12:15
                        update_vals['date_start'] = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
                    else:
                        # Standard format: 2025-05-26 12:15
                        update_vals['date_start'] = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
                except ValueError as ve:
                    # Try alternative formats
                    try:
                        # Try with seconds
                        if 'T' in date_str:
                            update_vals['date_start'] = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                        else:
                            update_vals['date_start'] = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        # Last fallback: let Odoo handle it
                        update_vals['date_start'] = date_str
                    
            if 'date_end' in post and post['date_end']:
                date_str = post['date_end']
                try:
                    if 'T' in date_str:
                        update_vals['date_end'] = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
                    else:
                        update_vals['date_end'] = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
                except ValueError:
                    try:
                        if 'T' in date_str:
                            update_vals['date_end'] = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                        else:
                            update_vals['date_end'] = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        update_vals['date_end'] = date_str
                    
            if 'therapist_start' in post and post['therapist_start']:
                date_str = post['therapist_start']
                try:
                    if 'T' in date_str:
                        update_vals['therapist_start'] = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
                    else:
                        update_vals['therapist_start'] = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
                except ValueError:
                    try:
                        if 'T' in date_str:
                            update_vals['therapist_start'] = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                        else:
                            update_vals['therapist_start'] = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        update_vals['therapist_start'] = date_str
                    
            if 'therapist_end' in post and post['therapist_end']:
                date_str = post['therapist_end']
                try:
                    if 'T' in date_str:
                        update_vals['therapist_end'] = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
                    else:
                        update_vals['therapist_end'] = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
                except ValueError:
                    try:
                        if 'T' in date_str:
                            update_vals['therapist_end'] = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                        else:
                            update_vals['therapist_end'] = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        update_vals['therapist_end'] = date_str
            
            # Handle assigned staff (many2many)
            # Check for both array-style and regular parameter names
            staff_param = None
            if 'assigned_staff_ids' in post:
                staff_param = post['assigned_staff_ids']
                param_name = 'assigned_staff_ids'
            elif 'assigned_staff_ids[]' in post:
                staff_param = post['assigned_staff_ids[]']
                param_name = 'assigned_staff_ids[]'
            
            if staff_param is not None:
                _logger.info(f"Raw {param_name} from form: {staff_param} (type: {type(staff_param)})")
                staff_ids = []
                if isinstance(staff_param, list):
                    # Handle list of values
                    staff_ids = [int(x) for x in staff_param if x]
                elif staff_param:
                    # Handle single value or comma-separated string
                    if ',' in str(staff_param):
                        # Comma-separated values from JavaScript workaround
                        staff_ids = [int(x.strip()) for x in str(staff_param).split(',') if x.strip()]
                    else:
                        # Single value
                        staff_ids = [int(staff_param)]
                _logger.info(f"Processed staff_ids: {staff_ids}")
                update_vals['assigned_staff_ids'] = [(6, 0, staff_ids)]
            else:
                _logger.info("No assigned_staff_ids parameter in post data")
                # If no staff selected, clear the field
                update_vals['assigned_staff_ids'] = [(6, 0, [])]
            
            # Update the event
            event.write(update_vals)
            
            return http.request.redirect(f'/my/event/{event_id}?success=1')
            
        except Exception as e:
            # Clean error message to prevent redirect issues with newlines
            error_msg = str(e).replace('\n', ' ').replace('\r', ' ')
            return http.request.redirect(f'/my/event/{event_id}/edit?error={error_msg}')
