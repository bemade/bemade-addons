from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo import http, _, fields
from odoo.exceptions import UserError, AccessError
from datetime import datetime, timedelta
from .access_control_mixin import AccessControlMixin
import logging
import pytz

_logger = logging.getLogger(__name__)


class EventsPortal(CustomerPortal, AccessControlMixin):
    
    def _parse_portal_datetime(self, val):
        """Parse a datetime-local string coming from the portal form as a user-local
        datetime, then convert it to UTC for storage in fields.Datetime.

        Accepts formats like 'YYYY-MM-DDTHH:MM' or 'YYYY-MM-DD HH:MM' (with or without seconds).
        Returns an RFC-compliant UTC datetime string via fields.Datetime.to_string().
        """
        if not val:
            return False
        # 1) Parse to a naive datetime
        dt = None
        try:
            if 'T' in val:
                dt = datetime.strptime(val, '%Y-%m-%dT%H:%M')
            else:
                dt = datetime.strptime(val, '%Y-%m-%d %H:%M')
        except ValueError:
            try:
                if 'T' in val:
                    dt = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S')
                else:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # As a last resort, let Odoo try to coerce whatever string was provided
                return val

        # 2) Determine user's timezone
        tz_name = (http.request.context.get('tz') if http.request and http.request.context else None) or \
                  (http.request.env.user.tz if http.request else None) or 'UTC'
        try:
            user_tz = pytz.timezone(tz_name)
        except Exception:
            user_tz = pytz.UTC

        # 3) Localize and convert to UTC
        local_dt = user_tz.localize(dt)
        utc_dt = local_dt.astimezone(pytz.UTC)

        # 4) Return as proper string for fields.Datetime
        return fields.Datetime.to_string(utc_dt)
    
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
                   date_from=None, date_to=None, sortby=None, search=None, no_default_dates=None, **kw):
        """Main events view with filtering and pagination"""
        
        # Check access
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        if not (is_therapist or is_coach or user.has_group('base.group_system')):
            raise AccessError(_("You don't have access to events."))
        
        # Default date filter: from yesterday, similar to internal "Upcoming" behavior
        # Only apply when user did not specify any date filters AND no explicit clear flag
        if not date_from and not date_to and not no_default_dates:
            try:
                # Use date (not datetime) input format 'YYYY-MM-DD' for the portal date picker
                yesterday = (fields.Date.today() - timedelta(days=1))
                date_from = fields.Date.to_string(yesterday)
            except Exception:
                # Fallback using datetime in rare cases
                date_from = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')

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
                     'date_to': date_to, 'sortby': sortby, 'search': search, 'no_default_dates': no_default_dates},
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
            'no_default_dates': no_default_dates,
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

        # Helper to format dt for datetime-local inputs in user's tz
        def _format_dt_local(dt):
            if not dt:
                return ''
            try:
                tz_name = (http.request.context.get('tz') if http.request and http.request.context else None) or \
                          (http.request.env.user.tz if http.request else None) or 'UTC'
                user_tz = pytz.timezone(tz_name)
            except Exception:
                user_tz = pytz.UTC
            # Odoo stores as UTC-naive; localize to UTC first
            if dt.tzinfo is None:
                utc_dt = pytz.UTC.localize(dt)
            else:
                utc_dt = dt.astimezone(pytz.UTC)
            local_dt = utc_dt.astimezone(user_tz)
            return local_dt.strftime('%Y-%m-%dT%H:%M')

        values = {
            'event': event,
            'teams': teams,
            'treatment_professionals': treatment_professionals,
            'venues': venues,
            'page_name': 'event_edit',
            # Preformatted local datetime values
            'date_start_local': _format_dt_local(event.date_start),
            'date_end_local': _format_dt_local(event.date_end),
            'therapist_start_local': _format_dt_local(event.therapist_start),
            'therapist_end_local': _format_dt_local(event.therapist_end),
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
                update_vals['date_start'] = self._parse_portal_datetime(post['date_start'])
                    
            if 'date_end' in post and post['date_end']:
                update_vals['date_end'] = self._parse_portal_datetime(post['date_end'])
                    
            if 'therapist_start' in post and post['therapist_start']:
                update_vals['therapist_start'] = self._parse_portal_datetime(post['therapist_start'])
                    
            if 'therapist_end' in post and post['therapist_end']:
                update_vals['therapist_end'] = self._parse_portal_datetime(post['therapist_end'])
            
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

    @http.route(['/my/event/create'], type='http', auth='user', website=True)
    def create_event_form(self, **kw):
        """Display event creation form - only accessible to therapists"""
        # Access: only therapists (or system) can create
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to create events."))

        # Options for form
        teams = self._get_accessible_teams() if not user.has_group('base.group_system') else http.request.env['sports.team'].search([])
        treatment_professionals = self._get_treatment_professionals()
        venues = http.request.env['res.partner'].search([('is_venue', '=', True)])

        values = {
            'teams': teams,
            'treatment_professionals': treatment_professionals,
            'venues': venues,
            'page_name': 'event_create',
        }
        return http.request.render('bemade_sports_clinic.portal_event_create', values)

    @http.route(['/my/event/create/submit'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def create_event_submit(self, **post):
        """Handle event creation - only accessible to therapists"""
        # Access: only therapists (or system) can create
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to create events."))

        try:
            create_vals = {}

            # Required fields
            if 'name' in post and post['name']:
                create_vals['name'] = post['name']
            else:
                raise UserError(_('Event name is required.'))

            if 'team_id' in post and post['team_id']:
                create_vals['team_id'] = int(post['team_id'])
            else:
                raise UserError(_('Team is required.'))

            # Optional simple fields
            if 'description' in post:
                create_vals['description'] = post['description']
            if 'venue_id' in post and post['venue_id']:
                create_vals['venue_id'] = int(post['venue_id'])
            if 'event_type' in post:
                create_vals['event_type'] = post['event_type']
            if 'state' in post:
                create_vals['state'] = post['state']

            # Datetime fields
            def _parse_dt(val):
                return self._parse_portal_datetime(val)

            if 'date_start' in post and post['date_start']:
                create_vals['date_start'] = _parse_dt(post['date_start'])
            else:
                raise UserError(_('Event start time is required.'))

            if 'date_end' in post and post['date_end']:
                create_vals['date_end'] = _parse_dt(post['date_end'])
            else:
                raise UserError(_('Event end time is required.'))

            # Default therapist times to event times if not provided
            if post.get('therapist_start'):
                create_vals['therapist_start'] = _parse_dt(post['therapist_start'])
            else:
                create_vals['therapist_start'] = create_vals['date_start']

            if post.get('therapist_end'):
                create_vals['therapist_end'] = _parse_dt(post['therapist_end'])
            else:
                create_vals['therapist_end'] = create_vals['date_end']

            # Assigned staff (same handling as save_event)
            staff_param = None
            if 'assigned_staff_ids' in post:
                staff_param = post['assigned_staff_ids']
            elif 'assigned_staff_ids[]' in post:
                staff_param = post['assigned_staff_ids[]']

            staff_ids = []
            if staff_param is not None:
                _logger.info(f"Raw assigned_staff_ids from form: {staff_param} (type: {type(staff_param)})")
                if isinstance(staff_param, list):
                    staff_ids = [int(x) for x in staff_param if x]
                elif staff_param:
                    if ',' in str(staff_param):
                        staff_ids = [int(x.strip()) for x in str(staff_param).split(',') if x.strip()]
                    else:
                        staff_ids = [int(staff_param)]
            create_vals['assigned_staff_ids'] = [(6, 0, staff_ids)]

            # Task creation is handled by the model's create() default logic

            event = http.request.env['sports.event'].create(create_vals)

            # Surgical sudo: create management task as superuser to bypass project/analytic ACLs
            try:
                event.sudo().create_management_task()
            except Exception as task_err:
                _logger.warning(f"Portal task creation failed for event {event.id}: {task_err}")

            return http.request.redirect(f'/my/event/{event.id}?created=1')

        except Exception as e:
            # Preserve user input and re-render the create form with errors
            error_msg = str(e).replace('\n', ' ').replace('\r', ' ')

            # Options for form
            user = http.request.env.user
            teams = self._get_accessible_teams() if not user.has_group('base.group_system') else http.request.env['sports.team'].search([])
            treatment_professionals = self._get_treatment_professionals()
            venues = http.request.env['res.partner'].search([('is_venue', '=', True)])

            # Assigned staff selected
            staff_param = post.get('assigned_staff_ids') or post.get('assigned_staff_ids[]')
            assigned_staff_selected = []
            if staff_param is not None:
                if isinstance(staff_param, list):
                    assigned_staff_selected = [int(x) for x in staff_param if x]
                elif staff_param:
                    if ',' in str(staff_param):
                        assigned_staff_selected = [int(x.strip()) for x in str(staff_param).split(',') if x.strip()]
                    else:
                        try:
                            assigned_staff_selected = [int(staff_param)]
                        except Exception:
                            assigned_staff_selected = []

            values = {
                'teams': teams,
                'treatment_professionals': treatment_professionals,
                'venues': venues,
                'page_name': 'event_create',
                'error': error_msg,
                # Preserve simple fields
                'name': post.get('name') or '',
                'event_type': post.get('event_type') or '',
                'state': post.get('state') or 'confirmed',
                'team_id_selected': int(post['team_id']) if post.get('team_id') else None,
                'venue_id_selected': int(post['venue_id']) if post.get('venue_id') else None,
                'description_html': post.get('description') or '',
                # Preserve datetime-local fields as entered (local strings)
                'date_start_local': post.get('date_start') or '',
                'date_end_local': post.get('date_end') or '',
                'therapist_start_local': post.get('therapist_start') or '',
                'therapist_end_local': post.get('therapist_end') or '',
                # Preserve assigned staff selections
                'assigned_staff_selected': assigned_staff_selected,
            }
            return http.request.render('bemade_sports_clinic.portal_event_create', values)

    @http.route(['/my/venue/create'], type='json', auth='user', website=True, methods=['POST'], csrf=False)
    def create_venue_ajax(self, **post):
        """Create a venue partner record via AJAX for portal users.
        Uses surgical sudo to avoid ACL/record rule issues, but restricts fields strictly.
        """
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (is_therapist or user.has_group('base.group_system')):
            return {'success': False, 'error': _("You don't have permission to create venues.")}

        name = (post.get('name') or '').strip()
        if not name:
            return {'success': False, 'error': _('Venue name is required.')}

        try:
            vals = {
                'name': name,
                'is_company': True,
                'is_venue': True,
                'type': 'other',
            }
            # Optional address fields
            for key in ['street', 'street2', 'city', 'zip']:
                if post.get(key):
                    vals[key] = post.get(key)

            # Optional country/state by id
            if post.get('country_id'):
                try:
                    vals['country_id'] = int(post.get('country_id'))
                except Exception:
                    pass
            if post.get('state_id'):
                try:
                    vals['state_id'] = int(post.get('state_id'))
                except Exception:
                    pass

            venue = http.request.env['res.partner'].sudo().create(vals)
            return {'success': True, 'id': venue.id, 'name': venue.name}
        except Exception as e:
            return {'success': False, 'error': str(e)}
