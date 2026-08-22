import urllib.parse
from datetime import date

from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo import http, _
from odoo.exceptions import UserError, AccessError, MissingError

from .access_control_mixin import AccessControlMixin

# /my/teams sort modes (task 1401). Keys are what the page posts and what
# res.users.teams_sort_mode stores; labels live in the template (translated).
TEAMS_SORT_MODES = ('activity', 'alpha', 'mine')
# /my/teams page size. 48 (owner, 2026-08-21): with « Mon ordre » a therapist
# should virtually never have to page — paging across a personal order is a
# chore, and the cards are light.
TEAMS_PAGE_SIZE = 48


class TeamStaffPortal(CustomerPortal, AccessControlMixin):
    def _prepare_home_portal_values(self, counters):
        rtn = super()._prepare_home_portal_values(counters)
        user = http.request.env.user
        teams_domain = self._prepare_teams_domain()
        players_domain = self._prepare_players_domain(teams_domain)
        rtn['teams_count'] = http.request.env['sports.team'].search_count(teams_domain)
        rtn['players_count'] = http.request.env['sports.patient'].search_count(
            players_domain)
        # mail.activity and sports.event ACLs only cover internal users,
        # portal coaches and portal TPs. Any other portal user (e.g. staff
        # role 'other') would 403 right at login if we counted
        # unconditionally (task 1222 dev-review fix, 2026-07-04).
        if (user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
                or user.has_group('bemade_sports_clinic.group_portal_team_coach')
                or user.has_group('base.group_user')):
            activities_domain = self._prepare_activities_domain()
            rtn['activities_count'] = http.request.env['mail.activity'].search_count(
                activities_domain)
            events_domain = self._prepare_events_domain()
            rtn['events_count'] = http.request.env['sports.event'].search_count(
                events_domain)
        # Timesheets count (therapists only)
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
        
        # Build team-based access domain for security filtering (task 1409:
        # activities live on patients and teams — no injury branch)
        return [
            '|',
            '&', '&',
            ('res_model', '=', 'sports.patient'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.team'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.id') or [0])
        ]

    # ------------------------------------------------------------------
    # /my/teams sorting (task 1401)
    # ------------------------------------------------------------------
    @staticmethod
    def _teams_sort_role():
        """Which role-scoped player-activity stamp orders THIS viewer's list.

        Same split as the team dashboard (team_management_portal): portal or
        internal treatment professionals and admins see the TP stamp; everyone
        else (coaches, role='other' staff) sees the coach-visible one — a
        coach's order must not move on TP-only activity (Law 25).
        """
        user = http.request.env.user
        if (user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
                or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
                or user.has_group('base.group_system')):
            return 'tp'
        return 'coach'

    @staticmethod
    def _teams_can_rank():
        """Who may keep a personal team order — exactly the groups holding an
        ACL on sports.team.user.rank. A role='other' portal user never gets the
        « Mon ordre » option (it would 403 on the first write)."""
        user = http.request.env.user
        return (
            user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
            or user.has_group('bemade_sports_clinic.group_portal_team_coach')
            or user.has_group('base.group_user')
        )

    def _teams_activity_order(self):
        # Postgres puts NULLs first on DESC; teams with no recorded player
        # activity must sort LAST, then alphabetically among equals.
        return 'last_player_activity_%s_at desc nulls last, name, id' % self._teams_sort_role()

    def _teams_order_for(self, mode):
        if mode == 'alpha':
            return 'name, id'
        return self._teams_activity_order()

    def _teams_resolve_sort(self, requested):
        """Resolve the effective sort mode and persist an explicit choice.

        Sticky per user (owner decision 5): an explicit ``?sort=`` becomes the
        stored preference; a visit without one uses the stored preference;
        with nothing stored the default is « Mon ordre » when the user already
        has ranks, else « Activité récente » (decision 6). ``mine`` is only
        available to users who may rank; anyone else silently gets activity.

        Returns ``(mode, previous_mode)`` — ``previous_mode`` is what the user
        was on before this request, used to seed a first « Mon ordre » from the
        order they were just looking at.
        """
        user = http.request.env.user
        can_rank = self._teams_can_rank()
        stored = user.teams_sort_mode or None
        if requested == 'mine' and not can_rank:
            requested = 'activity'
        if requested in TEAMS_SORT_MODES:
            mode = requested
            if mode != stored:
                try:
                    # Self-writable preference (SELF_WRITEABLE_FIELDS): a portal
                    # user may write this on their own record.
                    user.write({'teams_sort_mode': mode})
                except AccessError:
                    pass
        elif stored:
            mode = stored
        elif can_rank and http.request.env['sports.team.user.rank'].search_count(
                [('user_id', '=', user.id)], limit=1):
            mode = 'mine'
        else:
            mode = 'activity'
        if mode == 'mine' and not can_rank:
            mode = 'activity'
        previous = stored if stored in TEAMS_SORT_MODES else 'activity'
        return mode, previous

    def _teams_seed_personal_order(self, seed_mode):
        """First entry into « Mon ordre »: seed the ranks from the order the
        user was just looking at (acceptance 5), over the FULL visible set
        (not the current search subset, so an unfiltered list is complete)."""
        Teams = http.request.env['sports.team']
        Rank = http.request.env['sports.team.user.rank']
        user = http.request.env.user
        if Rank.search_count([('user_id', '=', user.id)], limit=1):
            return
        teams = Teams.search(self._prepare_teams_domain(),
                             order=self._teams_order_for(seed_mode))
        if teams:
            Rank._set_user_order(user, teams.ids)

    def _teams_personal_order(self, domain):
        """The FULL visible set in the user's personal order — ranked teams
        by rank, unranked appended in recent-activity order (acceptance 4).
        Resolved before the pager slices (acceptance 6)."""
        Teams = http.request.env['sports.team']
        teams = Teams.search(domain, order=self._teams_activity_order())
        return http.request.env['sports.team.user.rank']._resolve_user_order(
            http.request.env.user, teams)

    @http.route(route=['/my/teams', '/my/teams/page/<int:page>'], type='http', auth='user', website=True)
    def view_teams(self, page=1, search=None, sort=None, **kw):
        """ Display the list of teams that a portal user has access to.

        Optional `search` query param does an `ilike` on team name and
        the parent organization name — useful when a user has many
        accessible teams.

        Optional `sort` (task 1401): ``activity`` (most recent player
        activity first, the default), ``alpha`` (by name) or ``mine`` (the
        user's personal order, editable on the page). The choice is sticky per
        user. Ordering is applied to the FULL visible set before the pager
        slices — never to one page.
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
        sort_mode, previous_mode = self._teams_resolve_sort(sort)
        teams_count = Teams.search_count(domain)
        pgr_url_args = {'search': search_term} if search_term else {}
        pgr_url_args['sort'] = sort_mode
        step = TEAMS_PAGE_SIZE
        pgr = pager(url='/my/teams', total=teams_count,
                    page=page, step=step, scope=5,
                    url_args=pgr_url_args)
        # limit must be the page size, not the full result count — with the
        # pager advancing offset by the page size while limit spanned everything, page 2+
        # re-served the whole remaining list (duplicate teams across pages).
        if sort_mode == 'mine':
            self._teams_seed_personal_order(previous_mode)
            ordered = self._teams_personal_order(domain)
            page_teams = ordered[pgr['offset']:pgr['offset'] + step]
            teams = Teams.browse([team.id for team in page_teams])
        else:
            teams = Teams.search(domain,
                                 order=self._teams_order_for(sort_mode),
                                 offset=pgr['offset'],
                                 limit=step)
        return http.request.render(template='bemade_sports_clinic.portal_my_teams',
                                   qcontext={
                                       'teams_count': teams_count,
                                       'teams': teams,
                                       'pager': pgr,
                                       'page_name': 'my_teams',
                                       'search': search_term,
                                       'sort_mode': sort_mode,
                                       'can_rank': self._teams_can_rank(),
                                       'page': page,
                                       # "&search=..." to append to the sort
                                       # links so a search survives a re-sort.
                                       'search_qs': (
                                           '&' + urllib.parse.urlencode({'search': search_term})
                                           if search_term else ''),
                                   })

    @http.route(route=['/my/teams/reorder'], type='http', auth='user',
                website=True, methods=['POST'])
    def reorder_teams(self, **post):
        """Persist the user's personal team order (« Mon ordre », task 1401).

        ONE endpoint, two callers — the #1398 idiom:
        * drag posts ``order`` — the full team-id order, once, after the drop;
        * the up/down buttons post ``team_id`` + ``direction`` — the keyboard
          path, the no-JS path and the only path on a phone.
        Only teams in the user's own visible set are accepted; foreign ids are
        dropped. CSRF is enforced by the http POST route itself.
        """
        if not self._teams_can_rank():
            response = http.request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': _("You cannot keep a personal team order."),
            })
            response.status_code = 403
            return response
        Rank = http.request.env['sports.team.user.rank']
        user = http.request.env.user
        domain = self._prepare_teams_domain()
        visible = self._teams_personal_order(domain)
        visible_ids = [team.id for team in visible]

        search_term = (post.get('search') or '').strip()
        try:
            page = max(int(post.get('page') or 1), 1)
        except (TypeError, ValueError):
            page = 1
        anchor = ''

        raw_order = (post.get('order') or '').strip()
        if raw_order:
            ordered_ids = []
            for chunk in raw_order.split(','):
                chunk = chunk.strip()
                if chunk.isdigit() and int(chunk) in visible_ids:
                    ordered_ids.append(int(chunk))
            if ordered_ids:
                # The drag works on ONE page: splice that page's new order back
                # into the full list, so the other pages keep their places.
                page_set = set(ordered_ids)
                full = []
                inserted = False
                for team_id in visible_ids:
                    if team_id in page_set:
                        if not inserted:
                            full.extend(ordered_ids)
                            inserted = True
                    else:
                        full.append(team_id)
                Rank._set_user_order(user, full)
        else:
            direction = post.get('direction')
            try:
                team_id = int(post.get('team_id') or 0)
            except (TypeError, ValueError):
                team_id = 0
            if direction in ('up', 'down') and team_id in visible_ids:
                index = visible_ids.index(team_id)
                target = index - 1 if direction == 'up' else index + 1
                if 0 <= target < len(visible_ids):
                    visible_ids[index], visible_ids[target] = (
                        visible_ids[target], visible_ids[index])
                    Rank._set_user_order(user, visible_ids)
                anchor = '#team-%s' % team_id

        url = '/my/teams' if page == 1 else '/my/teams/page/%s' % page
        params = {'sort': 'mine'}
        if search_term:
            params['search'] = search_term
        return http.request.redirect(
            url + '?' + urllib.parse.urlencode(params) + anchor)

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

        # Task 1385: ONE batched presence query for the homogenized cards on this
        # page — which players have recent changes (the collapsed "changements
        # récents" hint) and which injuries changed (the static-section markers).
        # No per-player feed compute here; the full feed lazy-loads on expand.
        card_role = 'tp' if is_tp_admin else 'coach'
        presence = Patients._dashboard_card_presence(players, card_role)

        return http.request.render(
            template='bemade_sports_clinic.portal_my_players',
            qcontext={
                'players_count': total,
                'players': players,
                'accessible_ids': accessible_ids,
                'changed_player_ids': presence['players'],
                'changed_injury_ids': presence['injuries'],
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

    @http.route(route=['/my/player/<int:player_id>/recent-changes'], type='http',
                auth='user', website=True)
    def portal_player_recent_changes(self, player_id, **kw):
        """Task 1385: lazy-load fragment of one player's recent-changes feed for
        the homogenized portal card's expandable section.

        Fetched by portal_card_recent_changes.js when a card's <details> is
        opened, so the (per-player, mail-tracking-audit) change compute runs ONLY
        for cards the user actually opens — not for every card at page render.

        Access is enforced in code exactly like the other /my/player* routes
        (_check_access_to_patient: staff-on-team or admin), so no new security
        record is needed. The injury de-dup is applied server-side here: a change
        to an active injury already shown in the card's static section is dropped
        (it is marked there instead); only changes to injuries NOT shown up top,
        plus player-level changes, remain.
        """
        try:
            player = self._check_access_to_patient(int(player_id))
        except UserError as e:
            response = http.request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
        user = http.request.env.user
        is_tp = (user.has_group('base.group_system')
                 or user.has_group('bemade_sports_clinic.group_portal_treatment_professional'))
        role = 'tp' if is_tp else 'coach'
        Patients = http.request.env['sports.patient']
        cutoff = Patients._dashboard_window_cutoff()
        # The static section shows the active injuries the viewer can see (the
        # coach record rule already hides hidden-from-coaches ones). De-dup uses
        # exactly that set.
        shown_injury_ids = player.injury_ids.filtered(
            lambda i: i.stage == 'active').ids
        items = player._dashboard_change_items_deduped(role, cutoff, shown_injury_ids)
        return http.request.render(
            'bemade_sports_clinic.portal_card_recent_changes_fragment',
            {'items': items, 'player': player},
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
        # Clinic navigation context (task 1410): validated, silently dropped
        # when invalid. Drives the breadcrumbs + every link/return URL below.
        clinic_event = self._clinic_context(kw)

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

        # Activities tab (task 1222): the player's own activities. Since task
        # 1409 activities live on the patient only (the former injury-level
        # ones were moved here with a « [Injury: …] » summary prefix), so the
        # list is patient-scoped. mail.activity record rules already gate
        # broad access; constraining res_id to this player keeps the listing
        # team-scoped.
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
                    ('res_model', '=', 'sports.patient'),
                    ('res_id', '=', player.id),
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
            # Task 1408: the shared sudo helper — a plain search() here was
            # collapsed to "self" by base.res_users_rule_portal for portal TPs
            # (the owner's TP saw only herself on the player page).
            if is_treatment_prof:
                assignable_users = self._activity_assignable_users()
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

        # Show the direct-remove button ONLY when the viewer may actually remove
        # from this team (task 1260 — the single permission predicate), so it
        # never appears for someone the route will refuse (e.g. a doctor: holds a
        # portal-TP group but isn't a therapist on the team). Request Removal is
        # the fallback for any team staff who may NOT remove directly (coaches AND
        # non-therapist TPs), so no staffer is left with no way to act.
        env = http.request.env
        removal_team = (
            env['sports.team'].browse(removal_team_id)
            if removal_team_id else env['sports.team']
        )
        # Evaluate the predicate in the PORTAL user's env (http.request.env, not
        # sudo), on an empty patient recordset — it keys on env.user + team, not
        # on a specific patient, so this correctly asks "may THIS viewer remove
        # from this team".
        can_direct_remove = bool(
            removal_team_id and env['sports.patient']._may_remove_from_team(removal_team)
        )
        can_request_removal = bool(removal_team_id) and not can_direct_remove

        # Precompute tab-anchor return URLs (and url-encoded variants
        # for embedding in another URL's query string). Doing this in
        # Python avoids QWeb's t-attf %-format collisions with literal
        # %23/%26 sequences.
        # `ctx_qs` is the navigation-context tail (&team_id=…&clinic_id=…)
        # every link the page builds appends after its own first parameter,
        # so a sub-page reached from here knows both the team and the clinic
        # (task 1410) the user came from. Empty outside any context.
        ctx_qs = ''
        if team_context_id:
            ctx_qs += f'&team_id={team_context_id}'
        if clinic_event:
            ctx_qs += f'&clinic_id={clinic_event.id}'

        def _tab_url(tab):
            return f'/my/player?player_id={player.id}{ctx_qs}#{tab}'

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
                'clinic_event': clinic_event,
                'ctx_qs': ctx_qs,
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
