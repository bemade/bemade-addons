import urllib.parse
from datetime import date

from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo import http, _
from odoo.exceptions import UserError, AccessError, MissingError

from .access_control_mixin import AccessControlMixin


class TeamStaffPortal(CustomerPortal, AccessControlMixin):
    def _prepare_home_portal_values(self, counters):
        rtn = super()._prepare_home_portal_values(counters)
        teams_domain = self._prepare_teams_domain()
        players_domain = self._prepare_players_domain(teams_domain)
        activities_domain = self._prepare_activities_domain()
        events_domain = self._prepare_events_domain()
        rtn['teams_count'] = http.request.env['sports.team'].search_count(teams_domain)
        rtn['players_count'] = http.request.env['sports.patient'].search_count(
            players_domain)
        rtn['activities_count'] = http.request.env['mail.activity'].search_count(
            activities_domain)
        rtn['events_count'] = http.request.env['sports.event'].search_count(
            events_domain)
        # Timesheets count (therapists only)
        user = http.request.env.user
        if user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or user.has_group('base.group_system'):
            rtn['timesheets_count'] = http.request.env['sports.event.timesheet'].search_count([('user_id', '=', user.id)])
        return rtn

    @classmethod
    def _prepare_teams_domain(cls):
        user = http.request.env.user
        return [
            ('staff_ids.user_ids', '=', user.id),
        ]

    @classmethod
    def _prepare_players_domain(cls, teams_domain):
        team_ids = http.request.env['sports.team'].search(teams_domain).ids
        return [
            ('team_ids', 'in', team_ids),
        ]

    # _get_accessible_teams / _get_organizations / _prepare_events_domain removed:
    # they were shadowed by AccessControlMixin's (formerly events_portal's) versions
    # and never ran. The mixin now provides the single implementation. (Dead-route audit.)

    @classmethod
    def _prepare_activities_domain(cls):
        # Use controller-level team-based filtering for consistent security
        # Record rules provide broad CRUD access, controller enforces team-based security
        user = http.request.env.user
        partner = user.partner_id
        team_staff_rels = partner.team_staff_rel_ids
        
        # Build team-based access domain for security filtering
        return [
            '|', '|',
            '&', '&',
            ('res_model', '=', 'sports.patient'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.patient.injury'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.injury_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.team'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.id') or [0])
        ]

    @http.route(route=['/my/teams', '/my/teams/page/<int:page>'], type='http', auth='user', website=True)
    def view_teams(self, page=0, search=None, **kw):
        """ Display the list of teams that a portal user has access to.

        Optional `search` query param does an `ilike` on team name and
        the parent organization name — useful when a user has many
        accessible teams.
        """
        Teams = http.request.env['sports.team']
        domain = self._prepare_teams_domain()
        search_term = (search or '').strip()
        if search_term:
            domain = domain + [
                '|',
                ('name', 'ilike', search_term),
                ('parent_id.name', 'ilike', search_term),
            ]
        teams_count = Teams.search_count(domain)
        pgr_url_args = {'search': search_term} if search_term else None
        pgr = pager(url='/my/teams', total=teams_count,
                    page=page, step=10, scope=5,
                    url_args=pgr_url_args)
        teams = Teams.search(domain,
                             offset=pgr['offset'],
                             limit=teams_count)
        return http.request.render(template='bemade_sports_clinic.portal_my_teams',
                                   qcontext={
                                       'teams_count': teams_count,
                                       'teams': teams,
                                       'pager': pgr,
                                       'page_name': 'my_teams',
                                       'search': search_term,
                                   })

    # view_team (route '/my/team') removed: the bare '/my/team' route is served by
    # team_management_portal.portal_team_players (registered later, so it always won),
    # and this handler's only other route ('/my/team/page/<int:page>') was linked
    # nowhere. It was unreachable dead code. (Dead-route audit.)

    @http.route(route=['/my/players', '/my/players/page/<int:page>'], type='http', auth='user', website=True)
    def view_players(self, page=1, **kw):
        """Display the list of players the portal user has access to, with filters.

        Filters supported (GET params):
        - first_name (ilike)
        - last_name (ilike)
        - team_id (exact)
        - organization_id (team parent partner)
        - match_status (exact)
        - practice_status (exact)
        """
        Patients = http.request.env['sports.patient']
        user = http.request.env.user
        is_system = user.has_group('base.group_system')
        is_tp_admin = is_system or user.has_group(
            'bemade_sports_clinic.group_portal_treatment_professional')
        # Teams the user actually staffs (drives both accessibility and the
        # Add-to-Team target list). For a TP this is NOT "all teams": full
        # patient-record access requires a staff relationship (see
        # _check_access_to_patient), so the accessibility test must use the
        # staffed teams, not _get_accessible_teams().
        staff_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
        staff_team_ids = set(staff_teams.ids)

        # Base domain by accessible teams
        teams_domain = self._prepare_teams_domain()
        base_players_domain = self._prepare_players_domain(teams_domain)

        # Additional filters
        first_name = (kw.get('first_name') or '').strip()
        last_name = (kw.get('last_name') or '').strip()
        team_id = kw.get('team_id')
        organization_id = kw.get('organization_id')
        match_status = kw.get('match_status')
        practice_status = kw.get('practice_status')

        # Task 1225 / 640: when a TP/admin searches by name, broaden beyond the
        # user's own teams so out-of-team players are *findable* (to be added to
        # a team the user staffs). The per-record ir.rules would hide those
        # patients, so the identity-level lookup is done with sudo(); full
        # record access stays team-gated by view_player. The default (no name
        # search) listing and the home counter remain "your players" only.
        name_search = bool(first_name or last_name)
        broaden = is_tp_admin and name_search
        Patients_search = Patients.sudo() if broaden else Patients

        filters = []
        if first_name:
            filters.append(('first_name', 'ilike', first_name))
        if last_name:
            filters.append(('last_name', 'ilike', last_name))
        if team_id:
            try:
                filters.append(('team_ids', 'in', [int(team_id)]))
            except Exception:
                pass
        if organization_id:
            try:
                org_id = int(organization_id)
                # players whose any team has this parent organization
                team_ids = http.request.env['sports.team'].search([('parent_id', '=', org_id)]).ids
                filters.append(('team_ids', 'in', team_ids or [0]))
            except Exception:
                pass
        if match_status:
            filters.append(('match_status', '=', match_status))
        if practice_status:
            filters.append(('practice_status', '=', practice_status))

        domain = ([] if broaden else list(base_players_domain)) + filters

        # Count and pagination
        total = Patients_search.search_count(domain)
        pgr = pager(
            url='/my/players',
            total=total,
            page=page,
            step=self._items_per_page,
            url_args={
                'first_name': first_name,
                'last_name': last_name,
                'team_id': team_id,
                'organization_id': organization_id,
                'match_status': match_status,
                'practice_status': practice_status,
            },
        )

        # Query with ordering: last name, first name ASC
        players = Patients_search.search(
            domain,
            order='last_name asc, first_name asc',
            limit=self._items_per_page,
            offset=pgr['offset'],
        )

        # Per-row accessibility (task 1225): a player is openable only if the
        # user is a system admin or staffs one of the player's teams - exactly
        # _check_access_to_patient's rule. Inaccessible players (surfaced by the
        # broadened search) get an Add-to-Team action instead of a 403-bound
        # View link.
        if is_system:
            accessible_ids = set(players.ids)
        else:
            accessible_ids = {
                p.id for p in players
                if staff_team_ids.intersection(p.team_ids.ids)
            }
        # Teams offered in the Add-to-Team control: only the user's own staffed
        # teams, and only for users who may directly add (TP/admin). Linking to
        # one of these grants the user access afterwards.
        add_to_team_teams = staff_teams.sorted('name') if is_tp_admin else staff_teams.browse([])

        # Filter options
        teams = self._get_accessible_teams()
        organizations = self._get_organizations()
        match_status_selection = dict(Patients._fields['match_status'].selection)
        practice_status_selection = dict(Patients._fields['practice_status'].selection)

        return http.request.render(
            template='bemade_sports_clinic.portal_my_players',
            qcontext={
                'players_count': total,
                'players': players,
                'accessible_ids': accessible_ids,
                'add_to_team_teams': add_to_team_teams,
                'pager': pgr,
                'page_name': 'my_players',
                # filters current values
                'first_name': first_name,
                'last_name': last_name,
                'team_id': int(team_id) if team_id else None,
                'organization_id': int(organization_id) if organization_id else None,
                'match_status': match_status,
                'practice_status': practice_status,
                # options
                'teams': teams,
                'organizations': organizations,
                'match_status_selection': match_status_selection,
                'practice_status_selection': practice_status_selection,
            },
        )

    @http.route(route=['/my/player'], type='http',
                auth='user', website=True)
    def view_player(self, player_id, team_id=None,**kw):
        """ Display the active injuries for a given player. """
        player_id = int(player_id)
        team_id = team_id and int(team_id)
        # Team-gated record access (task 640): being findable in the broadened
        # player search does NOT grant access to the full record. Mirror the
        # edit/sub-routes — only users who staff one of the player's teams (or
        # admins) may open the detail page.
        try:
            player = self._check_access_to_patient(player_id)
        except UserError as e:
            response = http.request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
        team = team_id and http.request.env['sports.team'].browse(team_id)

        # Check if user is a treatment professional (portal version)
        user = http.request.env.user
        is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        

        
        # Show all injuries to treatment professionals, but only active ones to coaches
        if is_treatment_prof:
            injuries = player.injury_ids
        else:
            injuries = player.injury_ids.filtered(lambda r: r.stage == 'active')

        # Patient documents for Documents tab (primary association now on patient)
        patient_documents = http.request.env['sports.injury.document'].search([
            ('patient_id', '=', player.id)
        ], order='create_date desc, id desc')

        # Treatment notes for the new Notes tab (TPs only see this tab,
        # but always loading is cheap and avoids tab-conditional context).
        treatment_notes = http.request.env['sports.treatment.note'].search([
            ('patient_id', '=', player.id)
        ], order='date desc, id desc')

        # Activities tab (task 1222): the player's own activities AND the
        # activities of the injuries the user is allowed to see, merged into one
        # list. We scope injury activities to `injuries` (the role-filtered set
        # computed above — TPs see all, coaches see active only), so an activity
        # on an injury the user can't read never surfaces here. mail.activity
        # record rules already gate broad access; constraining res_id to this
        # player and its visible injuries keeps the listing team-scoped.
        #
        # IMPORTANT: only TPs and coaches hold ACLs on mail.activity[.type]
        # (see security/ir.model.access.csv). view_player is reachable by any
        # team staffer, including role='other' users who hold neither portal
        # group, so the search/types lookups MUST be gated or they raise
        # AccessError and 500 the whole player page. The Activities tab is
        # likewise hidden from those users in the template.
        can_use_activities = is_treatment_prof or user.has_group(
            'bemade_sports_clinic.group_portal_team_coach')
        player_activities = http.request.env['mail.activity']
        activity_types = http.request.env['mail.activity.type']
        default_activity_type = http.request.env['mail.activity.type']
        assignable_users = http.request.env['res.users']
        if can_use_activities:
            player_activities = http.request.env['mail.activity'].search(
                [
                    '|',
                    '&', ('res_model', '=', 'sports.patient'),
                    ('res_id', '=', player.id),
                    '&', ('res_model', '=', 'sports.patient.injury'),
                    ('res_id', 'in', injuries.ids or [0]),
                ],
                order='date_deadline asc',
            )

            # Data for the inline add-activity header (mirrors
            # create_activity_form for model='sports.patient').
            activity_types = http.request.env['mail.activity.type'].search([])
            default_activity_type = http.request.env.ref(
                'mail.mail_activity_data_todo', raise_if_not_found=False)
            if not default_activity_type:
                default_activity_type = http.request.env['mail.activity.type'].search(
                    [('category', '=', 'todo')], limit=1)
            # Assignable users: TPs may assign to any treatment professional
            # (portal or internal); coaches may only assign to themselves.
            if is_treatment_prof:
                portal_tp_group = http.request.env.ref(
                    'bemade_sports_clinic.group_portal_treatment_professional')
                internal_tp_group = http.request.env.ref(
                    'bemade_sports_clinic.group_sports_clinic_treatment_professional')
                assignable_users = http.request.env['res.users'].search([
                    ('group_ids', 'in', [portal_tp_group.id, internal_tp_group.id])
                ])
            else:
                assignable_users = user

        # Categories for patient document uploads
        categories = [
            ('medical', 'Medical'),
            ('medical_imaging', 'Medical Imaging'),
            ('prescription', 'Prescription'),
            ('other', 'Other'),
        ]

        # Create patient_info dictionary for protected fields (when user is a treatment professional)
        # No need for sudo() now that we have proper field-level access rights
        patient_info = {}
        if is_treatment_prof:
            # Include allergies and medical notes - direct access now that security is properly configured
            patient_info['allergies'] = player.allergies
            patient_info['team_info_notes'] = player.team_info_notes
        
        # Compute removal request visibility for coaches on the player detail view
        # Conditions:
        # - user is a coach, and
        #   - a valid team context is provided (user is staff on that team AND player belongs to that team), OR
        #   - player belongs to exactly one team and user is staff on that team
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        partner = user.partner_id
        staff_team_ids = set(partner.team_staff_rel_ids.mapped('team_id.id'))

        player_team_ids = set(player.team_ids.ids)
        player_team_count = len(player_team_ids)

        # Validate team context
        valid_team_context = False
        removal_team_id = None
        team_context_id = None
        if team:
            team_context_id = team.id
            if (team.id in staff_team_ids) and (team.id in player_team_ids):
                valid_team_context = True
                removal_team_id = team.id

        # Fallback: single team membership case
        if not valid_team_context and player_team_count == 1:
            sole_team_id = next(iter(player_team_ids)) if player_team_ids else None
            if sole_team_id and sole_team_id in staff_team_ids:
                removal_team_id = sole_team_id

        can_request_removal = bool(is_coach and removal_team_id)
        can_direct_remove = bool(is_treatment_prof and removal_team_id)

        # Precompute tab-anchor return URLs (and url-encoded variants
        # for embedding in another URL's query string). Doing this in
        # Python avoids QWeb's t-attf %-format collisions with literal
        # %23/%26 sequences.
        def _tab_url(tab):
            base = f'/my/player?player_id={player.id}'
            if team_context_id:
                base += f'&team_id={team_context_id}'
            return base + '#' + tab

        contacts_tab_return = _tab_url('contacts')
        documents_tab_return = _tab_url('documents')
        notes_tab_return = _tab_url('notes')
        injuries_tab_return = _tab_url('injuries')
        activities_tab_return = _tab_url('activities')
        contacts_tab_return_q = urllib.parse.quote(contacts_tab_return, safe='')

        add_contact_url = (
            f'/my/player/contact/add?patient_id={player.id}'
            f'&return_url={contacts_tab_return_q}'
        )

        return http.request.render(
            template='bemade_sports_clinic.portal_my_player_injuries',
            qcontext={
                'player': player,
                'injuries': injuries,
                'patient_documents': patient_documents,
                'treatment_notes': treatment_notes,
                'player_activities': player_activities,
                'activity_types': activity_types,
                'default_activity_type': default_activity_type,
                'assignable_users': assignable_users,
                'today': date.today().strftime('%Y-%m-%d'),
                'categories': categories,
                'team': team,
                'page_name': 'my_player',
                'is_treatment_prof': is_treatment_prof,
                'patient_info': patient_info,
                'can_request_removal': can_request_removal,
                'can_direct_remove': can_direct_remove,
                'removal_team_id': removal_team_id,
                'team_context_id': team_context_id,
                # Tab-anchor URLs for in-tab actions.
                'contacts_tab_return': contacts_tab_return,
                'documents_tab_return': documents_tab_return,
                'notes_tab_return': notes_tab_return,
                'injuries_tab_return': injuries_tab_return,
                'activities_tab_return': activities_tab_return,
                'contacts_tab_return_q': contacts_tab_return_q,
                'add_contact_url': add_contact_url,
            }
        )
