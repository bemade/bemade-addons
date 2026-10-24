import logging
from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from .access_control_mixin import AccessControlMixin, parse_portal_date
from .app_shell import AppShellMixin
from ..models import sc_app_nav, sc_app_roles
from datetime import date, timedelta
from urllib.parse import quote

_logger = logging.getLogger(__name__)



def _append_query(url, extra):
    """Append a query param to a URL WITHOUT breaking a #fragment.

    Tab return-URLs carry an anchor (…?player_id=7#activities); appending
    ?/&param after the fragment folds the param INTO the fragment, so the
    browser never activates the tab (candidate human-test finding,
    2026-07-10: adding an activity dumped the user back on the first tab).
    """
    base, _, frag = url.partition('#')
    sep = '&' if '?' in base else '?'
    return f'{base}{sep}{extra}' + (f'#{frag}' if frag else '')


class TaskManagementPortal(CustomerPortal, AccessControlMixin, AppShellMixin):
    """Controller for task management functionality in the portal"""

    # Access control methods now inherited from AccessControlMixin

    # ------------------------------------------------------------------
    # Assignee helpers (task 1402) — the single source of truth for who can
    # be assigned an activity from the portal, shared by the list page, the
    # create form, the edit form and both POST guards.
    # ------------------------------------------------------------------

    def _is_treatment_professional(self):
        """Whether the CURRENT user is a treatment professional — portal
        (group_portal_treatment_professional) or internal
        (group_sports_clinic_treatment_professional)."""
        user = request.env.user
        return (
            user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
            or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        )

    def _activity_record_teams(self, model, record):
        """Team scope of an activity's target record, for the advisory
        access warning (task 1402). Returns an empty recordset when no team
        scope is resolvable (-> no warning)."""
        if model == 'sports.patient':
            return record.team_ids
        if model == 'sports.team':
            return record
        if model == 'sports.event':
            return record.team_ids
        return request.env['sports.team']

    def _activity_assignee_team_access(self, model, record, users):
        """Advisory access map (task 1402): user_id -> whether that assignee
        has access to the record's team scope (partner is staff on one of
        the teams). Drives the non-blocking warning next to the assignee
        dropdown (create + edit pages). None when no team scope resolves.
        sudo(): the map needs staff lists of teams the REQUESTER may not
        staff (e.g. another team of the same patient), which the portal
        record rules would block; only booleans reach the template."""
        record_teams = self._activity_record_teams(model, record)
        if not record_teams:
            return None
        staff_partner_ids = set(record_teams.sudo().staff_ids.partner_id.ids)
        return {u.id: u.partner_id.id in staff_partner_ids for u in users}

    @staticmethod
    def _activity_team_access_domain(scope_teams):
        """The team-based access domain of the activities lists (patients,
        teams and events of ``scope_teams``). Task 1409: activities live on
        patients, teams and events only — no injury branch (an explicit
        ?model=sports.patient.injury filter therefore yields an empty
        list). Record rules provide broad CRUD access, the controller
        enforces team-based security."""
        return [
            '|', '|',
            '&', '&',
            ('res_model', '=', 'sports.patient'),
            ('res_id', '!=', False),
            ('res_id', 'in', scope_teams.mapped('patient_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.team'),
            ('res_id', '!=', False),
            ('res_id', 'in', scope_teams.ids or [0]),
            '&', '&',
            ('res_model', '=', 'sports.event'),
            ('res_id', '!=', False),
            ('res_id', 'in', scope_teams.mapped('event_ids.id') or [0])
        ]

    @http.route(['/my/activities/overdue/count'], type='http', auth='user', website=True,
                methods=['GET'], multilang=False, sitemap=False)
    def sc_activities_overdue_count(self, **kw):
        """Task 1592 — the app bar clock's badge as JSON ``{count: N}``: MY
        overdue activities, the same domain as « My Activities »
        (/my/activities: assigned to me AND in my team scope) with a
        deadline before today (the viewer's day). Polled by
        sc_live_count.js (at once, then every 60 s while the tab is
        visible), never computed on every page. Same gate as the clock: the
        staff app roles; anyone else gets a 403. Never cached."""
        env = request.env
        user = env.user
        roles = user._sc_app_roles()
        if not sc_app_roles.can('app.activity_clock', roles,
                                is_system=user.has_group('base.group_system')):
            response = request.make_json_response({'error': 'forbidden'}, status=403)
        else:
            domain = ['&', '&', ('user_id', '=', user.id),
                      ('date_deadline', '<', fields.Date.context_today(user))] \
                + self._activity_team_access_domain(self._activity_scope_teams())
            count = env['mail.activity'].search_count(domain)
            response = request.make_json_response({'count': count})
        response.headers['Cache-Control'] = 'no-store'
        return response

    @http.route(['/my/activities'], type='http', auth='user', website=True)
    def view_activities(self, model=None, res_id=None, simplified=False, team_id=None, **kw):
        """Display list of activities accessible to the current user through team relationships.

        When ``simplified`` is True (used by object-specific wrappers), the
        template renders a single list view without the global dashboard tabs.
        """
        user = request.env.user

        # Team scope (task 1577 review, 2026-09-29): every team for a clinic
        # administrator, the staffed teams for everyone else — the same rule
        # as the other lists; never a bare search([]) for a non-admin.
        scope_teams = self._activity_scope_teams()

        team_access_domain = self._activity_team_access_domain(scope_teams)

        # Activities are scoped strictly by the team-based access domain. We used to
        # OR-in `(user_id == self) AND res_model in [...]` so a portal user could see
        # activities personally assigned to them, but that left orphan assignee
        # activities (e.g. cron-created "Verify injury" tasks left over after a TP
        # was unstaffed from a team) visible while their related record was no
        # longer readable, causing 403s when the template browsed the related
        # injury for display. Aligning with the ir.rule keeps the listing
        # consistent with what the user can actually open.

        if model:
            domain = ['&', ('res_model', '=', model)] + team_access_domain
            if res_id:
                domain = ['&', ('res_id', '=', int(res_id))] + domain
        else:
            # Bare "My Activities" (/my/activities): scope to activities assigned
            # to the current user AND within their team-based access. The AND (not
            # OR) is deliberate — OR-ing user_id back in reintroduced orphan
            # assignee activities whose related record is unreadable (see comment
            # above), causing 403s. ANDing keeps My Activities to records the user
            # is assigned to AND can actually open. The per-context callers pass a
            # `model` and hit the branch above, keeping their broad context scope.
            domain = ['&', ('user_id', '=', user.id)] + team_access_domain
        
        # Search for activities with both assignment and team-based access control
        activities = request.env['mail.activity'].search(domain, order='date_deadline asc')
        
        # Group activities by model
        patient_activities = activities.filtered(lambda a: a.res_model == 'sports.patient')
        team_activities = activities.filtered(lambda a: a.res_model == 'sports.team')
        event_activities = activities.filtered(lambda a: a.res_model == 'sports.event')

        # Resolve optional context records for breadcrumbs
        context_team = None
        context_patient = None
        context_event = None

        if model and res_id:
            try:
                if model == 'sports.team':
                    context_team = request.env['sports.team'].browse(int(res_id))
                elif model == 'sports.patient':
                    context_patient = request.env['sports.patient'].browse(int(res_id))
                elif model == 'sports.event':
                    context_event = request.env['sports.event'].browse(int(res_id))
            except Exception:
                # If anything goes wrong resolving context, fall back to global view
                context_team = context_patient = context_event = None

        # Optional explicit team context (used when viewing a player's activities
        # from a team page). The wrapper routes have already validated team_id via
        # _check_team_access, so here we only need to resolve the record for breadcrumbs.
        if team_id:
            try:
                explicit_team = request.env['sports.team'].browse(int(team_id))
                if explicit_team.exists():
                    context_team = explicit_team
            except Exception:
                # If team resolution fails, keep existing context_team (if any)
                pass
        
        # Get activity types for filtering
        activity_types = request.env['mail.activity.type'].search([])
        
        # Available users for the reassign modal: the per-actor rule (task
        # 1500) — all TPs + coaches for a TP, own-teams staff for a coach.
        available_users = self._activity_assignable_users_for(user)

        values = {
            'activities': activities,
            'patient_activities': patient_activities,
            'team_activities': team_activities,
            'event_activities': event_activities,
            'activity_types': activity_types,
            'available_users': available_users,
            'page_name': 'activities',
            'today': date.today().strftime('%Y-%m-%d'),
            'show_assignee': bool(model),  # Show assignee column when viewing specific records
            'context_model': model,
            'context_res_id': res_id,
            'context_team': context_team,
            'context_patient': context_patient,
            'context_event': context_event,
            'simplified': bool(simplified),
        }
        
        # Task 1539: the app shell (switch on) or today's template (off) —
        # also for the /my/team/activities and /my/event/activities wrappers.
        if self._sc_app_shell_active():
            values.update(self._sc_activities_values(values))
        return self._sc_render('bemade_sports_clinic.portal_my_activities',
                               'bemade_sports_clinic.sc_app_activities', values)

    def _sc_activities_values(self, values):
        env = request.env
        today = fields.Date.context_today(env.user)
        activities = values['activities']
        overdue = activities.filtered(lambda a: a.date_deadline < today)
        due_today = activities.filtered(lambda a: a.date_deadline == today)
        planned = activities.filtered(lambda a: a.date_deadline > today)
        tab = request.params.get('tab')
        keys = ('all', 'overdue', 'today', 'planned')
        # Task 1592: from the app bar clock (?sc_clock=1) — the Overdue tab
        # when I have overdue activities, else All (deadline order, so the
        # overdue ones come first anyway). An explicit ?tab= wins.
        if tab not in keys and request.params.get('sc_clock'):
            tab = 'overdue' if overdue else 'all'
        base = request.httprequest.path
        args = {k: v for k, v in request.httprequest.args.items()
                if k not in ('tab', 'success', 'error', 'sc_clock')}
        query = '&'.join('%s=%s' % (k, quote(str(v), safe='')) for k, v in args.items())
        sep = '?' + query + '&' if query else '?'
        labels = {
            'all': env._("All (%(count)s)", count=len(activities)),
            'overdue': env._("Overdue (%(count)s)", count=len(overdue)),
            'today': env._("Today (%(count)s)", count=len(due_today)),
            'planned': env._("Planned (%(count)s)", count=len(planned)),
        }
        context_title = ''
        if values.get('context_patient'):
            context_title = values['context_patient'].name
        elif values.get('context_team'):
            context_title = values['context_team'].name
        elif values.get('context_event'):
            context_title = values['context_event'].display_name
        return {
            'today_date': today,
            'sc_activity_groups': {
                'all': activities, 'overdue': overdue, 'today': due_today, 'planned': planned},
            'sc_activity_tabs': [(key, labels[key], '%s%stab=%s' % (base, sep, key)) for key in keys],
            'sc_activity_active_tab': tab if tab in keys else 'all',
            'sc_activities_return': base + ('?' + query if query else ''),
            'sc_add_activity_url': (
                '/my/activity/create?model=%s&res_id=%s&return_url=%s' % (
                    quote(values['context_model'], safe=''),
                    quote(str(values['context_res_id']), safe=''),
                    quote(base + ('?' + query if query else ''), safe=''))
                if values.get('context_model') and values.get('context_res_id') else False),
            'sc_context_title': context_title,
            'sc_flash': self._sc_activity_flash(),
            # Task 1622: opened from the app bar clock — the page it was
            # tapped on (kept by the tab links), the way back. Not on the
            # record wrappers: they have their own parent.
            'sc_clock_from': False if values.get('simplified') else (
                sc_app_nav.clock_origin(request.params.get('sc_from')) or False),
        }

    @staticmethod
    def _sc_activity_flash():
        env = request.env
        params = request.params
        return {
            'success': {
                'activity_created': env._("Activity created successfully."),
                'activity_updated': env._("Activity updated."),
                'activity_reassigned': env._("Activity reassigned."),
                'activity_done': env._("Activity marked as done."),
                'activity_cancelled': env._("Activity deleted."),
            }.get(params.get('success')),
            'error': {
                'missing_fields': env._("Please fill in all required fields."),
                'invalid_user': env._("You cannot assign this activity to that user."),
                'not_allowed': env._("You cannot change this activity."),
            }.get(params.get('error')),
        }

    @http.route(['/my/activity/create'], type='http', auth='user', website=True)
    def create_activity_form(self, model=None, res_id=None, **kw):
        """Display form to create a new activity"""
        # Validate model and res_id (task 1409: no injury context — activities
        # are scheduled on the patient; an injury URL falls back to the list).
        valid_models = ['sports.patient', 'sports.team', 'sports.event']
        if model not in valid_models or not res_id:
            return request.redirect('/my/activities')
            
        record = self._check_access_to_task_model(model, res_id)

        # Get activity types
        activity_types = request.env['mail.activity.type'].search([])
        # Determine default activity type robustly
        # 1) Try canonical XML-ID from mail: 'mail.mail_activity_data_todo'
        default_activity_type = request.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        # 2) Fallback: category 'todo'
        if not default_activity_type:
            default_activity_type = request.env['mail.activity.type'].search([('category', '=', 'todo')], limit=1)
        # 3) Fallback: name contains 'todo'
        if not default_activity_type:
            default_activity_type = request.env['mail.activity.type'].search([('name', 'ilike', 'todo')], limit=1)
        
        # Users that can be assigned to activities: the per-actor rule of
        # _activity_assignable_users_for (task 1500) — a TP / admin may
        # assign to any TP or coach, a coach to the staff of their own
        # teams, anyone else only to themself. No unbounded search — the
        # advisory warning below flags assignees without team access.
        assignable_users = self._activity_assignable_users_for(request.env.user)

        # Advisory access map (task 1402) for the non-blocking warning.
        assignee_team_access = self._activity_assignee_team_access(
            model, record, assignable_users)
        
        # Prepare record name for display
        record_name = record.name if hasattr(record, 'name') else record.display_name
        
        # Clinic navigation context (task 1410): validated, dropped if invalid.
        clinic_event = self._clinic_context(kw) if model == 'sports.patient' else request.env['sports.event']

        # Default return URL (when no explicit return_url query param is provided)
        team_id_param = kw.get('team_id') or request.params.get('team_id')

        if model == 'sports.patient':
            # Optional team_id can be passed for team-aware navigation, but
            # explicit return_url (if present) always wins.
            if team_id_param:
                try:
                    team_id_int = int(team_id_param)
                except Exception:
                    team_id_int = None
                if team_id_int:
                    return_url = f'/my/player?player_id={res_id}&team_id={team_id_int}'
                else:
                    return_url = f'/my/player?player_id={res_id}'
            else:
                team_id_param = None
                return_url = f'/my/player?player_id={res_id}'
            return_url = self._with_clinic(return_url, clinic_event)
        elif model == 'sports.team':
            return_url = f'/my/team?team_id={res_id}'
        else:  # sports.event
            return_url = f'/my/event?event_id={res_id}'
            
        from datetime import date

        raw_return_url = kw.get('return_url')
        if raw_return_url and isinstance(raw_return_url, str) and '&amp;' in raw_return_url:
            raw_return_url = raw_return_url.replace('&amp;', '&')
        if not raw_return_url or raw_return_url in ('None', 'none', 'null', 'NULL'):
            raw_return_url = None
        # Task 1544: same-site paths only (was: any '/…', incl. '//host').
        raw_return_url = self._safe_return_url(raw_return_url, None)
    
        values = {
            'activity_types': activity_types,
            'assignable_users': assignable_users,
            'assignee_team_access': assignee_team_access,
            'record': record,
            'record_name': record_name,
            'model': model,
            'res_id': res_id,
            'default_user_id': request.env.user.id,
            'default_activity_type_id': default_activity_type.id if default_activity_type else False,
            'return_url': raw_return_url or return_url,
            'team_id': team_id_param if model == 'sports.patient' else None,
            'clinic_event': clinic_event,
            'page_name': 'create_activity',
            'today': date.today().strftime('%Y-%m-%d'),
        }
        
        # Task 1539: the app shell (switch on) or today's template (off).
        if self._sc_app_shell_active():
            values.update(self._sc_activity_form_values(values))
        return self._sc_render('bemade_sports_clinic.portal_create_activity',
                               'bemade_sports_clinic.sc_app_activity_form', values)

    @staticmethod
    def _sc_activity_form_values(values):
        """The advisory « no access to this team » ids (task 1402) for the
        shell's assignee select (sc_activities.js)."""
        access = values.get('assignee_team_access') or {}
        # The create and edit pages share the template: the keys only one
        # of them provides default to False (QWeb raises on unknown names).
        for key in ('activity', 'record_name', 'model', 'res_id', 'return_url', 'team_id',
                    'clinic_event', 'default_activity_type_id', 'default_user_id',
                    'assignable_users', 'available_users'):
            values.setdefault(key, False)
        return {
            'sc_no_access_ids': ' '.join(str(uid) for uid, ok in access.items() if not ok),
            'sc_flash': TaskManagementPortal._sc_activity_flash(),
        }

    @http.route(['/my/player/activities'], type='http', auth='user', website=True)
    def view_player_activities(self, player_id=None, team_id=None, **kw):
        """Back-compat redirect (task 1222).

        The player's activities (and its injuries') now live in an Activities
        tab on the player detail page, so this standalone page is retired. We
        keep the route and redirect to the player page's Activities tab anchor
        so old links/bookmarks/breadcrumbs keep working. Access is still gated
        via ``_check_access_to_patient`` (raises -> 403 for outsiders).
        """
        if not player_id:
            return request.redirect('/my/players')

        patient = self._check_access_to_patient(player_id)

        url = f'/my/player?player_id={patient.id}'
        if team_id:
            try:
                # Task 1577 review: a clinic admin's team context is kept
                # on any team; everyone else still needs a staff row.
                team = self._check_team_access(
                    team_id, check_staff=not self._is_clinic_admin())
                if team:
                    url += f'&team_id={team.id}'
            except UserError:
                pass

        return request.redirect(url + '#activities')

    @http.route(['/my/team/activities'], type='http', auth='user', website=True)
    def view_team_activities(self, team_id=None, **kw):
        """Object-specific wrapper: activities for a single team."""
        if not team_id:
            return request.redirect('/my/teams')

        # raises AccessError -> 403. Task 1577 review: a clinic admin opens
        # the activities of ANY team; everyone else needs a staff row.
        team = self._check_team_access(
            team_id, check_staff=not self._is_clinic_admin())
        return self.view_activities(model='sports.team', res_id=team.id, simplified=True)

    @http.route(['/my/injury/activities'], type='http', auth='user', website=True)
    def view_injury_activities(self, injury_id=None, team_id=None, **kw):
        """Back-compat redirect (task 1409).

        Activities are scheduled on the PATIENT only; the per-injury
        activities page is retired. Old links/bookmarks land on the player
        page's Activities tab. Access is still gated via
        ``_check_access_to_injury`` (raises -> 403 for outsiders).
        """
        if not injury_id:
            return request.redirect('/my/players')

        injury = self._check_access_to_injury(injury_id)

        url = f'/my/player?player_id={injury.patient_id.id}'
        if team_id:
            try:
                # Task 1577 review: a clinic admin's team context is kept
                # on any team; everyone else still needs a staff row.
                team = self._check_team_access(
                    team_id, check_staff=not self._is_clinic_admin())
                if team:
                    url += f'&team_id={team.id}'
            except UserError:
                pass

        return request.redirect(url + '#activities')

    @http.route(['/my/event/activities'], type='http', auth='user', website=True)
    def view_event_activities(self, event_id=None, **kw):
        """Object-specific wrapper: activities for a single event."""
        if not event_id:
            return request.redirect('/my/events')

        event = self._check_access_to_task_model('sports.event', event_id)

        return self.view_activities(model='sports.event', res_id=event.id, simplified=True)
    
    @http.route(['/my/activity/save'], type='http', auth='user', website=True, methods=['POST'])
    def create_activity_submit(self, **post):
        """Process form submission to create a new activity"""
        model = post.get('model')
        res_id = post.get('res_id')
        
        # Validate model and res_id (task 1409: no injury target)
        valid_models = ['sports.patient', 'sports.team', 'sports.event']
        if model not in valid_models or not res_id:
            return request.redirect('/my/activities')
            
        record = self._check_access_to_task_model(model, res_id)

        # Validate required fields
        activity_type_id = post.get('activity_type_id')
        summary = post.get('summary')
        user_id = post.get('user_id')
        date_deadline = post.get('date_deadline')
        
        def _sanitize_return_url(val, default):
            if val and isinstance(val, str) and '&amp;' in val:
                val = val.replace('&amp;', '&')
            if not val or val in ('None', 'none', 'null', 'NULL'):
                return default
            # Task 1544: same-site paths only (was: any '/…', incl. '//host').
            return self._safe_return_url(val, default)

        default_return_url = '/my/activities'
        if model == 'sports.patient':
            default_return_url = f'/my/player?player_id={int(res_id)}'
        elif model == 'sports.team':
            default_return_url = f'/my/team?team_id={int(res_id)}'
        elif model == 'sports.event':
            default_return_url = f'/my/event/{int(res_id)}'

        if not activity_type_id or not summary or not user_id or not date_deadline:
            return_url = _sanitize_return_url(post.get('return_url'), default_return_url)
            return request.redirect(_append_query(return_url, 'error=missing_fields'))
            
        # Check if the assigned user is valid: membership in the requester's
        # per-actor list (task 1500 — self is always in it, a TP gets all
        # TPs + coaches, a coach the staff of their own teams). Server-side
        # re-check, never trust the dropdown.
        try:
            assigned_user = request.env['res.users'].browse(int(user_id))
        except ValueError:
            assigned_user = request.env['res.users']
        if assigned_user not in self._activity_assignable_users_for(request.env.user):
            return_url = _sanitize_return_url(post.get('return_url'), default_return_url)
            return request.redirect(_append_query(return_url, 'error=invalid_user'))
            
        # Create the activity
        # Get model ID. sudo(): only the two PORTAL groups hold an ir.model
        # read ACL, so an internal TP would 403 here (task 1402); the model
        # name was already validated against valid_models above, so this
        # resolves a whitelisted name to an id and nothing more.
        model_id = request.env['ir.model'].sudo().search([('model', '=', model)], limit=1).id
        if not model_id:
            return_url = _sanitize_return_url(post.get('return_url'), default_return_url)
            return request.redirect(_append_query(return_url, 'error=invalid_model'))
            
        vals = {
            'activity_type_id': int(activity_type_id),
            'summary': summary,
            'note': post.get('note', ''),
            'user_id': int(user_id),
            'date_deadline': parse_portal_date(date_deadline),  # task 1640
            'res_model_id': model_id,
            'res_id': int(res_id),
        }
        
        # Create activity using sudo to bypass notification access issues for portal users
        # This is safe because we've already validated all inputs and access permissions above
        activity = request.env['mail.activity'].sudo().create(vals)
        
        # Redirect to the return URL or activities page, preserving optional team context
        return_url = _sanitize_return_url(post.get('return_url'), default_return_url)

        # For player activities, ensure team_id is not lost when coming
        # from a team-aware context. If a team_id was posted but is missing from
        # return_url, append it.
        if model == 'sports.patient':
            team_id = post.get('team_id')
            if team_id and 'team_id=' not in return_url:
                return_url = _append_query(return_url, f'team_id={int(team_id)}')
            # Same for the clinic nav context (task 1410), re-validated.
            return_url = self._with_clinic(return_url, self._clinic_context(post))

        return request.redirect(_append_query(return_url, 'success=activity_created'))
    
    @http.route(['/my/activity/update'], type='http', auth='user', website=True, methods=['POST'])
    def update_activity(self, **post):
        """Update an existing activity"""
        activity_id = post.get('activity_id')
        if not activity_id:
            return request.redirect('/my/activities')
            
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        # Check if the activity exists
        if not activity.exists():
            return request.redirect('/my/activities')
        
        # Task 1589: the one act rule (coaches: their own activities only).
        user = request.env.user
        if not self._activity_act_access(activity):
            return self._sc_activity_refused(post)

        # Update activity fields
        update_vals = {}
        if 'summary' in post:
            update_vals['summary'] = post['summary']
        if 'note' in post:
            update_vals['note'] = post['note']
        if 'date_deadline' in post:
            update_vals['date_deadline'] = parse_portal_date(post['date_deadline'])  # task 1640

        # Assignee change from the edit page (task 1500): honoured, and
        # validated with the SAME per-actor rule as save / reassign. Outside
        # the rule nothing is written and the edit page is re-shown with the
        # invalid_user error.
        if post.get('user_id'):
            try:
                new_user = request.env['res.users'].browse(int(post['user_id']))
            except ValueError:
                new_user = request.env['res.users']
            if new_user != activity.user_id:
                if new_user not in self._activity_assignable_users_for(user):
                    return request.redirect(_append_query(
                        f'/my/activity/{activity.id}/edit', 'error=invalid_user'))
                update_vals['user_id'] = new_user.id

        if update_vals:
            # sudo(): coaches hold a read-only mail.activity ACL; the team-
            # based access check above is the authorization (same as
            # /my/activity/reassign).
            activity.sudo().write(update_vals)
        
        # Redirect to activities page or return URL
        return_url = self._safe_return_url(post.get('return_url'), '/my/activities')
        return request.redirect(_append_query(return_url, 'success=activity_updated'))
    
    def _sc_activity_done_redirect(self, post, success):
        """Where complete / cancel / reschedule land. Today's modals post no
        ``return_url`` and keep landing on /my/activities exactly as before;
        the app shell's sheets (task 1539) post the page they were opened
        from (same-site paths only, task 1544) and get a confirmation."""
        return_url = self._safe_return_url(post.get('return_url'), None)
        if not return_url:
            return request.redirect('/my/activities')
        return request.redirect(_append_query(return_url, 'success=%s' % success))

    def _sc_activity_refused(self, post):
        """Task 1589: an act (complete / cancel / reschedule / reassign /
        update) refused by ``_activity_act_access`` — back to the page it was
        posted from (same-site paths only) or the list, with the error."""
        return_url = self._safe_return_url(post.get('return_url'), None) or '/my/activities'
        return request.redirect(_append_query(return_url, 'error=not_allowed'))

    @http.route(['/my/activity/complete'], type='http', auth='user', website=True, methods=['POST'])
    def complete_activity(self, **post):
        """Mark an activity as done"""
        activity_id = post.get('activity_id')
        if not activity_id:
            return request.redirect('/my/activities')
            
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        if not activity.exists():
            return request.redirect('/my/activities')
        # Task 1589: the one act rule, then sudo() — coaches hold a
        # read-only mail.activity ACL (sudo keeps the uid: the done message
        # is still authored by the user).
        if not self._activity_act_access(activity):
            return self._sc_activity_refused(post)

        feedback = post.get('feedback', '')
        activity.sudo().action_feedback(feedback=feedback)
        return self._sc_activity_done_redirect(post, 'activity_done')

    @http.route(['/my/activity/cancel'], type='http', auth='user', website=True, methods=['POST'])
    def cancel_activity(self, **post):
        """Cancel (delete) an activity."""
        activity_id = post.get('activity_id')
        if not activity_id:
            return request.redirect('/my/activities')

        activity = request.env['mail.activity'].browse(int(activity_id))
        if not activity.exists():
            return request.redirect('/my/activities')

        # Task 1589: the one act rule, then sudo() (coaches: read-only ACL).
        if not self._activity_act_access(activity):
            return self._sc_activity_refused(post)

        activity.sudo().unlink()
        return self._sc_activity_done_redirect(post, 'activity_cancelled')
    
    @http.route(['/my/activity/reschedule'], type='http', auth='user', website=True, methods=['POST'])
    def reschedule_activity(self, **post):
        """Reschedule an activity to a new date"""
        activity_id = post.get('activity_id')
        if not activity_id:
            return request.redirect('/my/activities')
            
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        if not activity.exists():
            return request.redirect('/my/activities')
        # Task 1589: whoever may act on the activity may reschedule it (was:
        # the assignee only), then sudo() (coaches: read-only ACL).
        if not self._activity_act_access(activity):
            return self._sc_activity_refused(post)

        new_deadline = post.get('new_deadline')
        if not new_deadline:
            return request.redirect('/my/activities')

        activity.sudo().write({'date_deadline': new_deadline})
        
        # Redirect to activities page
        return self._sc_activity_done_redirect(post, 'activity_updated')
    
    @http.route(['/my/activity/reassign'], type='http', auth='user', website=True, methods=['POST'])
    def reassign_activity(self, **post):
        """Reassign an activity to a different user"""
        activity_id = post.get('activity_id')
        new_user_id = post.get('new_user_id')
        
        if not activity_id or not new_user_id:
            return request.redirect('/my/activities')
            
        activity = request.env['mail.activity'].browse(int(activity_id))
        new_user = request.env['res.users'].browse(int(new_user_id))
        
        # Check if the activity exists and user has access to it
        if not activity.exists() or not new_user.exists():
            return request.redirect('/my/activities')
            
        # Verify the new user is in the REQUESTER's per-actor list (task
        # 1500): all TPs + coaches for a TP, the staff of their own teams for
        # a coach, nobody else for anyone else. Do not use has_group() on
        # arbitrary users; membership is checked against the helper's search
        # result to avoid security restrictions.
        if new_user not in self._activity_assignable_users_for(request.env.user):
            return request.redirect(_append_query(
                self._local_return_url(post.get('return_url'), '/my/activities'),
                'error=invalid_user'))
            
        # Task 1589: the one act rule (coaches: their own activities only).
        if not self._activity_act_access(activity):
            return self._sc_activity_refused(post)

        # Reassign the activity
        # Perform the actual reassignment with sudo to bypass mail.activity ACL
        # constraints for portal coaches. This is safe because we've already
        # validated:
        # - the activity exists
        # - the new user is in the requester's assignable list (task 1500)
        # - the current user may act on the activity (task 1589).
        activity.sudo().write({'user_id': new_user.id})
        
        # Determine return URL based on context
        return_url = self._safe_return_url(post.get('return_url'), '/my/activities')
        return request.redirect(_append_query(return_url, 'success=activity_reassigned'))

    @http.route(['/my/activity/<int:activity_id>/edit'], type='http', auth='user', website=True)
    def edit_activity_form(self, activity_id, **kw):
        """Display form to edit an existing activity"""
        activity = request.env['mail.activity'].browse(activity_id)
        
        # Check if the activity exists and user has access to it
        if not activity.exists():
            raise request.not_found()
        # Owner review 2026-10-11: in the app shell the activity is edited
        # in place (pencil card) on its page.
        if self._sc_app_shell_active():
            return request.redirect('/my/activity/%s' % activity.id)
            
        # Task 1589: editing is acting — the one act rule.
        user = request.env.user
        if not self._activity_act_access(activity):
            raise request.not_found()

        # Get activity types for the form
        activity_types = request.env['mail.activity.type'].search([
            ('res_model', 'in', ['sports.patient', 'sports.team', 'sports.event', False])
        ])
        
        # Available users for the assignee select: the per-actor rule (task
        # 1500), honoured by /my/activity/update under the same rule.
        available_users = self._activity_assignable_users_for(user)

        # Advisory access map (task 1402), as on the create page. sudo(): the
        # team-based access check above is the authorization; the record is
        # only read for its team scope.
        assignee_team_access = None
        if activity.res_model in ('sports.patient', 'sports.team', 'sports.event'):
            target = request.env[activity.res_model].sudo().browse(activity.res_id)
            if target.exists():
                assignee_team_access = self._activity_assignee_team_access(
                    activity.res_model, target, available_users)

        values = {
            'activity': activity,
            'activity_types': activity_types,
            'available_users': available_users,
            'assignee_team_access': assignee_team_access,
            'page_name': 'edit_activity',
            'today': date.today().strftime('%Y-%m-%d'),
        }
        
        # Task 1539: the app shell (switch on) or today's template (off).
        if self._sc_app_shell_active():
            values.update(self._sc_activity_form_values(values))
        return self._sc_render('bemade_sports_clinic.portal_edit_activity',
                               'bemade_sports_clinic.sc_app_activity_form', values)

    @http.route(['/my/activity/<int:activity_id>/attachment/<int:attachment_id>'],
                type='http', auth='user', methods=['GET'])
    def download_activity_attachment(self, activity_id, attachment_id, **kw):
        """Task 1586: download one attachment of an activity. Whoever may open
        the activity (``_activity_view_access``) may download its attachments;
        anyone else — and any attachment not of this activity — gets a 404.
        No access token: the URL grants nothing on its own."""
        activity = request.env['mail.activity'].browse(activity_id)
        if not activity.exists() or not self._activity_view_access(activity):
            raise request.not_found()
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
        if not attachment.exists() or attachment not in self._activity_attachments(activity):
            raise request.not_found()
        stream = request.env['ir.binary']._get_stream_from(attachment)
        return stream.get_response(as_attachment=True)

    @http.route(['/my/activity/<int:activity_id>'], type='http', auth='user', website=True)
    def view_activity_detail(self, activity_id, **kw):
        """Display detailed view of a specific activity"""
        activity = request.env['mail.activity'].browse(activity_id)
        
        # Check if the activity exists and user has access to it
        if not activity.exists():
            raise request.not_found()
            
        # Task 1586: one rule for the page and its attachment downloads.
        has_access = self._activity_view_access(activity)
        
        if not has_access:
            raise request.not_found()
        
        # Get related record details and context for breadcrumbs
        related_record = None
        related_record_name = ''
        context_team = None
        context_patient = None
        context_event = None

        if activity.res_model and activity.res_id:
            try:
                related_record = request.env[activity.res_model].browse(activity.res_id)
                if related_record.exists():
                    if activity.res_model == 'sports.patient':
                        context_patient = related_record
                        related_record_name = f"{related_record.first_name} {related_record.last_name}"
                    elif activity.res_model == 'sports.team':
                        context_team = related_record
                        related_record_name = related_record.display_name
                    elif activity.res_model == 'sports.event':
                        context_event = related_record
                        related_record_name = related_record.display_name
                    else:
                        related_record_name = related_record.display_name
            except Exception:
                pass
        
        # Get attachments for this activity (sudo inside: the access check
        # above is the authorization — coaches have no ir.attachment read on
        # mail.activity).
        attachments = self._activity_attachments(activity)
        
        from datetime import date
        
        values = {
            'activity': activity,
            'related_record': related_record,
            'related_record_name': related_record_name,
            'attachments': attachments,
            'page_name': 'activity_detail',
            'today': date.today().strftime('%Y-%m-%d'),
            'context_team': context_team,
            'context_patient': context_patient,
            'context_event': context_event,
        }
        
        # Task 1539: the app shell (switch on) or today's template (off).
        if self._sc_app_shell_active():
            # Task 1595: the related records' links, each gated by the
            # page it leads to (no link to a record the viewer may not open).
            related_links = self._sc_activity_related(activity)
            related_url = related_links[0]['url'] if related_links else False
            assignable = self._activity_assignable_users_for(request.env.user)
            users = (assignable | activity.sudo().user_id).sorted('name')
            values.update({
                'sc_related_url': related_url,
                'sc_related_links': related_links,
                'today_date': fields.Date.context_today(request.env.user),
                'sc_flash': self._sc_activity_flash(),
                # Owner review 2026-10-11: the pencil card's assignee choices.
                # Task 1589: pencil + Cancel / Reschedule / Done follow the
                # one act rule.
                'sc_activity_editable': self._activity_act_access(activity),
                'sc_activity_user_options': [(u.id, u.name) for u in users],
            })
        return self._sc_render('bemade_sports_clinic.portal_activity_detail',
                               'bemade_sports_clinic.sc_app_activity_detail', values)
