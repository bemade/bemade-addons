from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from .access_control_mixin import AccessControlMixin, parse_portal_date, sc_past_deadline_message
from .app_shell import AppShellMixin, sc_app_page
import logging
from datetime import date, timedelta
from urllib.parse import urlparse
from dateutil.relativedelta import relativedelta
from werkzeug.exceptions import Forbidden

from odoo.tools import format_date, format_datetime

_logger = logging.getLogger(__name__)

# Task 1663: « Annonce archivée — Annuler » (the toast lasts ~8 s, like the
# status pills' undo; the server allows a little more for the page load).
SC_ANNOUNCEMENT_UNDO_KEY = 'sc_announcement_undo'
SC_ANNOUNCEMENT_UNDO_SECONDS = 30

# Task 1389: rows per page on the full digest-history archive page.
DIGEST_HISTORY_PAGE_SIZE = 20
# Task 1421: roster tab sort modes -> ORM order. « status » is the historical
# default (stored sort_order key shared with the backend team form); « number »
# uses the stored jersey_sort helper (numeric, blanks last).
ROSTER_SORT_ORDERS = {
    'status': 'sort_order, last_name, first_name',
    'number': 'jersey_sort, last_name, first_name',
}

# Task 1542: dot / chip tone of a player's stage in the app shell rows.
SC_STAGE_TONES = {'no_play': 'red', 'practice_ok': 'yellow', 'healthy': 'green'}


class TeamManagementPortal(CustomerPortal, AccessControlMixin, AppShellMixin):
    
    # Access control methods now inherited from AccessControlMixin

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
                'message': _("Your request to remove %s from the team has been submitted to the team's head therapist.") % patient.name,
                'sticky': False,
            }
            
            return request.redirect(f"/my/team/{team_id}")
            
        except Exception as e:
            _logger.error("Error requesting player removal: %s", str(e), exc_info=True)
            error_message = _("Error requesting removal: %s") % self._user_error_text(e, 'team')
            return request.redirect(f"/my/team/{team_id}?error={error_message}".replace(' ', '+'))
    
    @http.route(['/my/player/<int:player_id>/request_removal'],
                type='http', auth="user", website=True, methods=['POST'])
    def portal_request_player_removal_any_team(self, player_id, **post):
        """Task 1664: the player page's « Request Removal » when the player
        is on several of the viewer's teams — the sheet posts the chosen
        ``team_id``; the same checks as the per-team route (which it calls)."""
        team_id = post.pop('team_id', '') or ''
        if not str(team_id).isdigit():
            request.session['notification'] = {
                'type': 'warning', 'title': '',
                'message': _("Please choose the team."),
                'sticky': False,
            }
            return request.redirect('/my/player?player_id=%s' % int(player_id))
        return self.portal_request_player_removal(int(team_id), player_id, **post)

    @http.route(['/my/team/<int:team_id>/player/<int:player_id>/remove'],
               type='http', auth="user", website=True, methods=['POST'])
    def portal_remove_player(self, team_id, player_id, **post):
        """
        Directly remove a player from the team.

        Removal authority is the SAME policy the internal path enforces: the
        team's therapist or head therapist (either TP group), or a system admin
        (task 1260). Coaches and doctors use the Request Removal flow instead.
        The permission check lives in the model (``remove_from_team`` ->
        ``_may_remove_from_team``), NOT here, so the portal and internal paths
        cannot diverge.
        """
        try:
            # _check_team_access is VISIBILITY only (can this user see the team
            # at all) — a separate concern from removal AUTHORITY, which the
            # model check below enforces.
            team = self._check_team_access(team_id)

            patient = request.env['sports.patient'].browse(int(player_id))
            if not patient.exists():
                raise MissingError(_("Player not found"))

            if team not in patient.team_ids:
                raise ValidationError(_("Player is not a member of this team"))

            # Route through the PUBLIC remove_from_team so the built-in
            # permission check actually runs (the old code called the private
            # _remove_from_team, which skips every check — the 1260 gap). No
            # sudo: the model check must see the real user.
            result = patient.remove_from_team(team.id, clear_pending=True)

            # Store success message in session for display after redirect
            request.session['notification'] = {
                'type': 'success',
                'title': _('Player Removed'),
                'message': _('%s has been successfully removed from the team.') % patient.sudo().name,
                'sticky': False,
            }

            return request.redirect(f"/my/team/{team_id}")

        except AccessError as e:
            # A coach or doctor (or a TP who is not a therapist on THIS team)
            # is not allowed to remove directly — point them at Request Removal
            # rather than showing the generic failure text (task 1260). The
            # model's AccessError message already names the request flow.
            _logger.info("Portal player removal denied: %s", str(e))
            request.session['notification'] = {
                'type': 'warning',
                'title': _('Removal Not Permitted'),
                'message': _(
                    "You don't have permission to remove players from this team "
                    "directly. Please use the 'Request Removal' action instead — "
                    "it notifies the team's head therapist."
                ),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")

        except Exception as e:
            # Don't put the raw exception (often multi-line) in the redirect URL:
            # newlines in a Location header raise a ValueError -> 500. Use a session
            # notification instead, like the success path.
            _logger.error("Error removing player: %s", str(e), exc_info=True)
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Error'),
                'message': _("Could not remove the player. Please try again or contact an administrator."),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
    
    @http.route(['/my/team/<int:team_id>/add_player',
                 '/my/team/<int:team_id>/player/add_link'],
                type='http', auth="user", website=True, methods=['GET'])
    @sc_app_page
    def portal_add_player_form(self, team_id, **kw):
        """Task 1541: old links / bookmarks of the legacy add-player pages —
        the team page's Players tab with the app's « Add a player » panel
        open (``add=1``; the page itself checks the team access)."""
        return request.redirect(
            '/my/team?team_id=%s&tab=players&add=1' % int(team_id), code=301)

    def _roster_resolve_sort(self, requested):
        """Effective roster sort mode; an explicit ``?sort=`` becomes the
        user's sticky preference (res.users.roster_sort_mode, self-writable —
        same contract as the /my/teams sort, task 1401). Unknown or absent →
        the stored preference, else « status »."""
        user = request.env.user
        stored = user.roster_sort_mode if user.roster_sort_mode in ROSTER_SORT_ORDERS else None
        if requested in ROSTER_SORT_ORDERS:
            if requested != stored:
                try:
                    user.write({'roster_sort_mode': requested})
                except AccessError:
                    pass
            return requested
        return stored or 'status'

    @http.route(['/my/team', '/my/team/<int:team_id>'], type='http', auth="user", website=True)
    @sc_app_page
    def portal_team_players(self, team_id=None, sort=None, tab=None, **kw):
        """Display the list of players for a team.

        Canonical public URL shape is /my/team?team_id=<id> to align with
        breadcrumbs and other portal links. The route also accepts
        /my/team/<int:team_id> but all redirects and templates should use
        the query-string form.
        """
        try:
            if not team_id:
                # If no team_id is provided in the path, fall back to query string
                team_id = request.httprequest.args.get('team_id')
                if not team_id:
                    # If still no team_id, redirect to the teams list
                    return request.redirect('/my/teams')

            team = self._check_team_access(team_id)
            
            # Get all players for the team, sorted by status severity so the
            # most concerning players (injured/limited) surface first, then by
            # name. Ordering is driven by the stored `sort_order` key on
            # sports.patient (single source of truth, shared with the backend
            # team-form Players list), so the two surfaces can never drift.
            # Task 1421: « Sort: Status · Number » on the roster tab, sticky
            # per user; the dashboard tab keeps its own score order below.
            roster_sort_mode = self._roster_resolve_sort(sort)
            players = request.env['sports.patient'].search([
                ('team_ids', 'in', [team.id]),
                ('active', '=', True)
            ], order=ROSTER_SORT_ORDERS[roster_sort_mode])

            # Check user permissions for UI elements
            is_treatment_prof = self._is_treatment_professional()
            is_admin = request.env.user.has_group('base.group_system')
            is_team_staff = team.staff_ids.filtered(
                lambda s: request.env.user.partner_id in s.user_ids.partner_id
            )
            
            # Activities tab (task 1223): team-LEVEL activities only. We strictly
            # scope to res_model='sports.team'/res_id=team.id so a team player's
            # (sports.patient) or injury's (sports.patient.injury) activities are
            # NOT mixed into the team tab. Only fetched for roles holding
            # mail.activity ACLs (TP / coach / internal) — a staff member with
            # role 'other' would 403 the whole page otherwise (dev-review
            # 2026-07-04 round 2).
            can_use_activities = (
                is_treatment_prof or is_admin
                or request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
                or request.env.user.has_group('base.group_user')
            )
            team_activities = request.env['mail.activity']
            activity_types = request.env['mail.activity.type']
            assignable_users = request.env.user
            default_activity_type = None
            if can_use_activities:
                team_activities = request.env['mail.activity'].search([
                    ('res_model', '=', 'sports.team'),
                    ('res_id', '=', team.id),
                ], order='date_deadline asc')
                activity_types = request.env['mail.activity.type'].search([])
                # Assignable users for the add-activity header / reassign modal:
                # the per-actor rule (task 1500) — TPs and admins may assign to
                # any TP or coach, a coach to the staff of their own teams.
                # Task 1408: the shared sudo helper — a plain search() here was
                # collapsed to "self" by base.res_users_rule_portal for portal TPs.
                assignable_users = self._activity_assignable_users_for(request.env.user)
                default_activity_type = request.env.ref(
                    'mail.mail_activity_data_todo', raise_if_not_found=False)

            # Dashboard tab (task 1272): role-scoped, recency-domained, score-
            # ordered subset of the roster. A portal TP (or admin/internal) sees
            # the TP rollups; a coach sees the coach rollups — a coach never sees
            # internal-note or hidden-injury activity (Law 25), because the coach
            # fields are only ever bumped by coach-visible changes.
            dashboard_role = 'tp' if (is_treatment_prof or is_admin) else 'coach'
            Patient = request.env['sports.patient']
            cutoff = Patient._dashboard_window_cutoff()
            stamp_field = 'dashboard_last_activity_%s' % dashboard_role
            score_field = 'dashboard_score_%s' % dashboard_role
            dashboard_players = players.filtered(
                lambda p: p[stamp_field] and p[stamp_field] >= cutoff
            ).sorted(key=lambda p: p[score_field], reverse=True)
            # Task 1385: the per-player change feed no longer renders eagerly as a
            # sibling of the card — it lazy-loads inside each homogenized card's
            # expandable <details> (route /my/player/<id>/recent-changes). Here we
            # run only the ONE batched presence query across the whole roster to
            # drive the collapsed "changements récents" hint and the static-section
            # injury markers. The expensive per-player mail-tracking compute now
            # happens solely for cards the user actually opens.
            presence = Patient._dashboard_card_presence(players, dashboard_role, cutoff)
            # Team-level upcoming events — same configurable window as the
            # backend dashboard and the morning briefing (task 1533).
            upcoming_events_days = request.env['sports.team']._dashboard_upcoming_events_days()
            now = fields.Datetime.now()
            horizon = now + relativedelta(days=upcoming_events_days)
            upcoming_events = request.env['sports.event'].search([
                ('team_ids', 'in', [team.id]),
                ('date_start', '>=', now),
                ('date_start', '<=', horizon),
                ('state', '!=', 'cancelled'),
            ], order='date_start asc')

            # Task 1416: the team's temporary staff rows (dated grants + event
            # coverage) for the read-only « Temporary staff » block. Staff names
            # and roles only; sudo because the portal staff rule scopes rows
            # to the viewer and the viewer already staffs this team.
            temp_staff_rows = team.sudo().temp_staff_ids.sorted(
                key=lambda r: (r.source != 'temp', r.partner_id.name or ''))

            values = {
                # Use my_teams so existing breadcrumbs logic renders
                # "Teams / <Team Name>" for team detail pages.
                'page_name': 'my_teams',
                'team': team,
                'players': players,
                'roster_sort_mode': roster_sort_mode,
                # A sort change reloads the page: land on the roster tab, not
                # the (default) dashboard tab.
                'active_tab': (
                    'players' if sort in ROSTER_SORT_ORDERS
                    # Task 1500 staging check: activity add/reassign return here
                    # with tab=activities so the user lands back on that tab.
                    else tab if tab in ('dashboard', 'players', 'activities')
                    else 'dashboard'
                ),
                'temp_staff_rows': temp_staff_rows,
                # Dashboard tab context (task 1272)
                'dashboard_role': dashboard_role,
                'dashboard_players': dashboard_players,
                # Task 1385: batched presence for the homogenized cards (both the
                # dashboard tab and the roster tab reuse the same card).
                'changed_player_ids': presence['players'],
                'changed_injury_ids': presence['injuries'],
                'dashboard_window_hours': Patient._dashboard_window_hours(),
                'upcoming_events': upcoming_events,
                # Task 1533: the copy states the live window. Whole sentences
                # translated here (one msgid each) rather than QWeb fragments
                # split around a <t t-esc/>.
                'upcoming_events_days': upcoming_events_days,
                'upcoming_events_window_label': request.env._(
                    "(next %(days)s days)", days=upcoming_events_days),
                'upcoming_events_empty_label': request.env._(
                    "No upcoming events in the next %(days)s days.",
                    days=upcoming_events_days),
                # Canonical URL used by pager and templates
                'default_url': f'/my/team?team_id={team.id}',
                'user_has_group': request.env.user.has_group,  # Pass the has_group method to template
                'user': request.env.user,
                'is_treatment_prof': is_treatment_prof or is_admin,
                # Whether THIS viewer may action removals on this team (task 1260):
                # gates the pending-removals alert so it shows only to those who can
                # actually review/remove, not to any portal TP (e.g. a doctor).
                'can_remove_on_team': request.env['sports.patient']._may_remove_from_team(team),
                'is_team_staff': bool(is_team_staff),
                # Activities tab context
                'can_view_activities': can_use_activities,
                'team_activities': team_activities,
                'activity_types': activity_types,
                'assignable_users': assignable_users,
                'available_users': assignable_users,  # reassign modal in activity_list_table
                'default_activity_type_id': default_activity_type.id if default_activity_type else False,
                'default_user_id': request.env.user.id,
                'today': date.today().strftime('%Y-%m-%d'),
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
                # Task 1744: the activity add panel's refusals in words.
                values['error'] = {
                    'past_deadline': sc_past_deadline_message(request.env),
                    'missing_fields': _("Please fill in all required fields."),
                    'invalid_user': _("You cannot assign this activity to that user."),
                }.get(error, error)
            
            # Task 1542: the app shell (switch on) or today's template, byte
            # for byte (switch off). The shell-only values are computed only
            # when the shell renders.
            values.update(self._sc_team_values(team, values))
            return self._sc_render('bemade_sports_clinic.sc_app_team', values)
            
        except (AccessError, MissingError) as e:
            # 1577 review: never the raw exception text in the URL / on the
            # page — log it, land on /my/teams with the clean message.
            self._user_error_text(e, 'team')
            return request.redirect('/my/teams?error=team_denied')

    # ------------------------------------------------------------------
    # Task 1542 — the team page in the app shell
    # ------------------------------------------------------------------
    def _sc_player_row(self, player, team, stage_labels, with_position=True, extras=None):
        """One roster / dashboard row: « #12 Last, First », stage dot + chip,
        position; links to the player page like the legacy card.
        Task 1593: ``extras`` (``_sc_player_row_extras``, computed once for
        the whole page) adds the legacy card's content — training
        recommendation, « Retour prévu », the lazy expanded detail; no team
        links on a team's own page (as legacy)."""
        stage = player.stage or 'healthy'
        position = player.position if with_position else False
        if extras is None:
            extras = self._sc_player_row_extras(player, team_links=False, team=team)
        return dict(extras[player.id], **{
            'id': player.id,
            'title': player._portal_list_name(),
            'subtitle': position or '',
            'dot': SC_STAGE_TONES.get(stage, 'green'),
            'chip': stage_labels.get(stage, ''),
            'url': '/my/player?player_id=%s&team_id=%s' % (player.id, team.id),
            'pending_removal': bool(player.pending_removal),
        })

    def _sc_team_values(self, team, values):
        """Shell-only render values for ``sc_app_team`` — built from the
        legacy values (same role filtering), never re-deriving them."""
        env = request.env
        user = env.user
        stage_labels = dict(
            env['sports.patient']._fields['stage']._description_selection(env))
        show_position = team.show_position_on_dashboard
        # « Recent changes » lists only players with something to show (the
        # ⚡ presence rule). A recent activity stamp whose changes net to
        # nothing (owner review 2026-10-11) is not a change: such a red or
        # yellow player joins « Other players to watch » instead.
        changed = set(values.get('changed_player_ids') or ())
        quiet = values['dashboard_players'].filtered(
            lambda p: p.id not in changed and p.stage in ('no_play', 'practice_ok'))
        watched = (team.dashboard_watchlist_patient_ids | quiet).sorted(
            key=lambda p: (p.sort_order, p.last_name or '', p.first_name or ''))
        # Task 1593: the rows' legacy-card content for every listed player
        # at once (no per-row queries); no team links on the team's own page.
        # Task 1634: the Match / Practice pills are quick-change dropdowns for
        # a status editor (the cards' status line, in place).
        extras = self._sc_player_row_extras(
            values['dashboard_players'] | watched | values['players'],
            team_links=False, team=team, status_edit=self._sc_status_editable())
        dashboard_rows = []
        for player in values['dashboard_players'].filtered(lambda p: p.id in changed):
            row = self._sc_player_row(player, team, stage_labels, show_position, extras)
            row['changed'] = True
            # Task 1626: the card is a player row like the others; its
            # « Details » loads the player's change detail, not the plain
            # row detail.
            row['detail_url'] = '/my/player/%s/recent-changes?detail=1&team_id=%s' % (
                player.id, team.id)
            dashboard_rows.append(row)
        watch_rows = [
            self._sc_player_row(player, team, stage_labels, show_position, extras)
            for player in watched
        ]
        roster_rows = [
            self._sc_player_row(player, team, stage_labels, extras=extras)
            for player in values['players']
        ]
        tz = user.tz or env.context.get('tz')
        kinds = dict(env['sports.event']._fields['event_type']._description_selection(env))
        upcoming_rows = [{
            'when': format_datetime(env, event.date_start, tz=tz,
                                    dt_format='EEE d MMM · HH:mm'),
            'kind': kinds.get(event.event_type, ''),
            'name': event.name or '',
            'url': '/my/event/%s' % event.id,
        } for event in values['upcoming_events']]
        can_add_directly = self._is_tp_or_system()
        org = team.sudo().parent_id.name or ''
        return {
            'sc_team_org': org,
            'sc_dashboard_rows': dashboard_rows,
            # Task 1655: the inline « create a player » panel (team pre-filled).
            'sc_player_add': self._sc_player_add_panel(team, 'sc_add_player', 'team.add_player'),
            'sc_watch_rows': watch_rows,
            'sc_roster_rows': roster_rows,
            'sc_upcoming_rows': upcoming_rows,
            'sc_pending_count': sum(1 for row in roster_rows if row['pending_removal']),
            'sc_can_add_directly': can_add_directly,
            'sc_can_edit_announcement': team._user_can_edit_announcement(),
            # Task 1663: right after an archive, its « Annuler » toast.
            'sc_announcement_undo': (
                self._sc_announcement_undo(team)
                if request.httprequest.args.get('announcement_archived') else None),
            'sc_announcement_deadline': (
                format_date(env, team.announcement_deadline)
                if team.announcement_deadline else ''),
            # Task 1719: the compact « Jusqu'au <date> » line.
            'sc_announcement_until': (
                env._("Until %(date)s", date=format_date(env, team.announcement_deadline))
                if team.announcement_deadline else ''),
            'sc_team_url': '/my/team?team_id=%s' % team.id,
            # Task 1635: the Activities tab counts what its panel lists.
            'sc_team_activities_badge': self._sc_activity_tab_badge(values['team_activities']),
            'sc_window_label': env._("(last %(hours)s h)",
                                     hours=values.get('dashboard_window_hours')),
            'sc_pending_label': env._(
                "%(count)s player(s) with a pending removal request.",
                count=sum(1 for row in roster_rows if row['pending_removal'])),
        }

    def _digest_for_viewer(self, team_id, digest_id):
        """Access + role gate shared by the snapshot page and its body
        fragment (tasks 1267, 1614): ``(team, digest, role)``.

        Only a team staff member (or a treatment professional / admin) may read
        a snapshot (non-member -> 403); a digest of another team -> 404
        (``MissingError``). The role is resolved exactly as the live dashboard
        does: a portal TP (or internal/admin) gets the TP view, everyone else the
        coach view.
        """
        try:
            # Visibility gate — same membership check as the live team page. A
            # non-member raises AccessError, surfaced as a real 403.
            team = self._check_team_access(team_id)
        except AccessError:
            raise Forbidden(
                _("You don't have permission to view this team's digest."))
        # sudo: the team gate above is the access rule; another team's digest
        # is « not found », never an access error.
        digest = request.env['sports.team.digest'].sudo().browse(int(digest_id)).exists()
        if not digest or digest.team_id.id != team.id:
            raise MissingError(_("This digest does not exist."))
        is_treatment_prof = self._is_treatment_professional()
        is_admin = request.env.user.has_group('base.group_system')
        role = 'tp' if (is_treatment_prof or is_admin) else 'coach'
        return team, digest, role

    @http.route(['/my/team/<int:team_id>/digest/<int:digest_id>'],
                type='http', auth="user", website=True)
    @sc_app_page
    def portal_team_digest(self, team_id, digest_id, **kw):
        """Historical view of one stored team-digest snapshot (task 1267).

        Law 25: the stored ``item_data`` is re-gated at read by the viewer's role
        (coach -> external only; TP -> all) — never frozen HTML. Access mirrors
        the live team dashboard: only a team staff member (or a treatment
        professional / admin) may view it; anyone else gets a 403.
        """
        try:
            team, digest, role = self._digest_for_viewer(team_id, digest_id)
        except MissingError:
            return request.not_found()

        players = digest._render_for_role(role)
        values = {
            'page_name': 'my_teams',
            'team': team,
            'digest': digest,
            'players': players,
            # Task 1270 (slice F): the frozen announcement rides in item_data;
            # it is all-staff content, so both roles see it.
            'announcement': (digest.item_data or {}).get('announcement'),
            'default_url': f'/my/team?team_id={team.id}',
        }
        # team_digest_render is rendered unchanged inside the app card.
        values['sc_digest_date'] = format_date(request.env, digest.snapshot_date)
        return self._sc_render('bemade_sports_clinic.sc_app_team_digest', values)

    @http.route(['/my/team/<int:team_id>/digest/<int:digest_id>/body'],
                type='http', auth="user", website=True)
    def portal_team_digest_body(self, team_id, digest_id, **kw):
        """Task 1614: one snapshot's body alone (no layout, never cached), the
        lazy body of its date in the app's digest history. Same gate and same
        role re-gated ``team_digest_render`` as the snapshot page."""
        try:
            _team, digest, role = self._digest_for_viewer(team_id, digest_id)
        except MissingError:
            return request.not_found()
        values = {
            'request': request,
            'digest': digest,
            'players': digest._render_for_role(role),
            'announcement': (digest.item_data or {}).get('announcement'),
        }
        html = request.env['ir.ui.view']._render_template(
            'bemade_sports_clinic.sc_digest_body', values)
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'),
        ])

    def _sanitize_local_back(self, back, team_id):
        """Open-redirect guard for the digest-history backlink (task 1389).

        Only a bare local ``/my/...`` path is honoured; anything carrying a
        scheme, a host, a protocol-relative ``//`` prefix, a backslash trick or a
        ``..`` traversal falls back to the team dashboard. Returns path (+ query)
        only, dropping any fragment.
        """
        default = '/my/team/%d' % int(team_id)
        if not back or not isinstance(back, str):
            return default
        if back.startswith('//') or '\\' in back or '..' in back:
            return default
        parsed = urlparse(back)
        if parsed.scheme or parsed.netloc:
            return default
        if not parsed.path.startswith('/my/'):
            return default
        return parsed.path + (('?' + parsed.query) if parsed.query else '')

    @http.route(['/my/team/<int:team_id>/digest-history',
                 '/my/team/<int:team_id>/digest-history/page/<int:page>'],
                type='http', auth="user", website=True)
    @sc_app_page
    def portal_team_digest_history(self, team_id, page=1, back=None,
                                   preview=None, **kw):
        """Task 1389: navigable history of a team's daily digest snapshots —
        every retained snapshot (date desc), paged, with a validated-local
        backlink; each date expands in place (task 1614).

        The list exposes ONLY snapshot dates — no content — so it is
        audience-safe as-is; the per-snapshot ``/digest/<id>`` render re-gates
        coach (external only) vs TP (internal + external). Membership is enforced
        exactly like the single-snapshot route (non-member -> 403).

        Task 1541: the legacy modal fragment (``?preview=1``, and the
        ``/digest-history/recent`` sibling, no longer routed) is gone: 404.
        """
        if preview:
            raise request.not_found()
        try:
            team = self._check_team_access(team_id)
        except MissingError:
            return request.not_found()
        except AccessError:
            raise Forbidden(
                _("You don't have permission to view this team's digest history."))

        Digest = request.env['sports.team.digest'].sudo()
        # Full paginated page.
        domain = [('team_id', '=', team.id)]
        total = Digest.search_count(domain)
        safe_back = self._sanitize_local_back(back, team.id)
        pgr = pager(
            url='/my/team/%d/digest-history' % team.id,
            total=total,
            page=int(page),
            step=DIGEST_HISTORY_PAGE_SIZE,
            url_args={'back': safe_back},
        )
        digests = Digest.search(
            domain,
            order='snapshot_date desc',
            limit=DIGEST_HISTORY_PAGE_SIZE,
            offset=pgr['offset'],
        )
        values = {
            'page_name': 'my_teams',
            'team': team,
            'digests': digests,
            'pager': pgr,
            'back_url': safe_back,
        }
        # Task 1614: each date expands in place (lazy body) with its
        # counts as the subtitle — a coach's re-gated (see _sc_counts).
        role = ('tp' if (self._is_treatment_professional()
                         or request.env.user.has_group('base.group_system'))
                else 'coach')
        values['sc_digest_rows'] = [{
            'id': d.id,
            'label': format_date(request.env, d.snapshot_date),
            'subtitle': d._sc_counts_label(role),
            'url': '/my/team/%d/digest/%d' % (team.id, d.id),
            'body_url': '/my/team/%d/digest/%d/body' % (team.id, d.id),
        } for d in digests]
        return self._sc_render('bemade_sports_clinic.sc_app_team_digest_history', values)

    def _announcement_error_redirect(self, team_id, message):
        """Redirect back to the team page with a flash error (task 1407)."""
        return request.redirect(
            f"/my/team?team_id={team_id}&error=" + message.replace(' ', '+')
        )

    @http.route(['/my/team/<int:team_id>/announcement'],
                type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_team_announcement(self, team_id, **post):
        """Post/edit the team announcement from the portal (task 1270). The
        model write guard enforces TP-only authorship; a non-TP submitting the
        form (they never see it) is redirected with an error.

        Task 1407: the role guard's refusal (not a TP on this team) is told
        apart from every OTHER AccessError (ACL / record rule — the failure
        that silently killed the feature for portal TPs since #1270), so the
        message the user sees is honest. The guard predicate is the model's
        own ``_user_can_edit_announcement`` — no portal-local copy of the
        role policy.
        """
        try:
            team = self._check_team_access(team_id, check_staff=True)
            if not team._user_can_edit_announcement():
                return self._announcement_error_redirect(
                    team_id,
                    _("Only treatment professionals can edit the team announcement."),
                )
            body = (post.get('announcement') or '').strip()
            # Task 1640: a malformed deadline (« 202610-10-10 ») gets a clear
            # message, not « Error saving announcement. ».
            try:
                deadline = parse_portal_date(post.get('announcement_deadline'))
            except ValidationError as e:
                return self._announcement_error_redirect(team_id, e.args[0])
            team.write({
                'announcement': body or False,
                'announcement_deadline': deadline,
            })
            return request.redirect(f"/my/team?team_id={team_id}")
        except AccessError as e:
            _logger.warning(
                "Team announcement save refused for user %s on team %s: %s",
                request.env.user.id, team_id, e,
            )
            return self._announcement_error_redirect(
                team_id,
                _("You don't have permission to edit the team announcement."),
            )
        except Exception as e:
            _logger.error("Error saving team announcement: %s", str(e), exc_info=True)
            return self._announcement_error_redirect(
                team_id, _("Error saving announcement.")
            )

    @http.route(['/my/team/<int:team_id>/announcement/dismiss'],
                type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_team_announcement_dismiss(self, team_id, **post):
        """Dismiss (clear) the team announcement from the portal (task 1270).
        TP-only, enforced by action_dismiss_announcement's write guard. Task
        1407: same guard-vs-other AccessError distinction as the post route."""
        try:
            team = self._check_team_access(team_id, check_staff=True)
            if not team._user_can_edit_announcement():
                return self._announcement_error_redirect(
                    team_id,
                    _("Only treatment professionals can dismiss the team announcement."),
                )
            # Task 1663: what « Annuler » puts back (this session only).
            before = {
                'team_id': team.id,
                'user_id': request.env.user.id,
                'body': team.announcement or '',
                'deadline': fields.Date.to_string(team.announcement_deadline) or False,
                'author_id': team.announcement_author_id.id or False,
                'date': fields.Datetime.to_string(team.announcement_date) or False,
            }
            team.action_dismiss_announcement()
            history = request.env['sports.team.note.history'].sudo().search(
                [('team_id', '=', team.id)], order='id desc', limit=1)
            if before['body'] and history.action == 'dismiss':
                before['history_id'] = history.id
                request.session[SC_ANNOUNCEMENT_UNDO_KEY] = before
            return request.redirect(f"/my/team?team_id={team_id}&announcement_archived=1")
        except AccessError as e:
            _logger.warning(
                "Team announcement dismiss refused for user %s on team %s: %s",
                request.env.user.id, team_id, e,
            )
            return self._announcement_error_redirect(
                team_id,
                _("You don't have permission to dismiss the team announcement."),
            )
        except Exception as e:
            _logger.error("Error dismissing team announcement: %s", str(e), exc_info=True)
            return request.redirect(f"/my/team?team_id={team_id}")

    def _sc_announcement_undo(self, team):
        """Task 1663: the pending « Annuler » of this user's last archive of
        THIS team's announcement (``request.session``), or None — when it is
        another team's, another user's, past the window, or anything changed
        the announcement since (a newer history row, a new text)."""
        payload = request.session.get(SC_ANNOUNCEMENT_UNDO_KEY)
        if not isinstance(payload, dict) or payload.get('team_id') != team.id:
            return None
        if payload.get('user_id') != request.env.user.id:
            return None
        History = request.env['sports.team.note.history'].sudo()
        history = History.browse(payload.get('history_id') or 0).exists()
        latest = History.search([('team_id', '=', team.id)], order='id desc', limit=1)
        if not history or history != latest or history.action != 'dismiss':
            return None
        if history.author_id != request.env.user:
            return None
        window = timedelta(seconds=SC_ANNOUNCEMENT_UNDO_SECONDS)
        if not history.note_datetime or fields.Datetime.now() - history.note_datetime > window:
            return None
        if (team.sudo().announcement or '').strip():
            return None
        return payload

    @http.route(['/my/team/<int:team_id>/announcement/restore'],
                type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_team_announcement_restore(self, team_id, **post):
        """Task 1663: « Annonce archivée — Annuler »: put back the
        announcement this user just archived (same text, deadline, author and
        date; the history gets « Restaurée »). Same right as the archive (a
        therapist of the team / an admin), the same user, within the window,
        nothing changed since. No email (none is sent for an announcement)."""
        back = f"/my/team?team_id={team_id}"
        try:
            team = self._check_team_access(team_id, check_staff=True)
            if not team._user_can_edit_announcement():
                return self._announcement_error_redirect(
                    team_id, _("Only treatment professionals can edit the team announcement."))
            payload = self._sc_announcement_undo(team)
            if not payload:
                request.session['notification'] = {
                    'type': 'warning', 'title': '',
                    'message': _("This announcement can no longer be restored."),
                    'sticky': False,
                }
                return request.redirect(back)
            team.with_context(sc_announcement_restore=True).write({
                'announcement': payload['body'],
                'announcement_deadline': payload.get('deadline') or False,
                'announcement_author_id': payload.get('author_id') or request.env.user.id,
                'announcement_date': payload.get('date') or fields.Datetime.now(),
            })
            request.session.pop(SC_ANNOUNCEMENT_UNDO_KEY, None)
            request.session['notification'] = {
                'type': 'success', 'title': '',
                'message': _("Announcement restored."),
                'sticky': False,
            }
            return request.redirect(back)
        except AccessError as e:
            _logger.warning("Team announcement restore refused for user %s on team %s: %s",
                            request.env.user.id, team_id, e)
            return self._announcement_error_redirect(
                team_id, _("You don't have permission to edit the team announcement."))

    # Task 1581: the announcement history action -> (chip tone, state); the
    # labels are built in _sc_announcement_history_entries (babel extracts
    # them from the _() calls there).
    SC_ANNOUNCEMENT_ACTIONS = {
        'set': ('green', None),
        'edit': ('ghost', None),
        'dismiss': ('ghost', 'archived'),
        'restore': ('green', None),
    }

    def _sc_announcement_history_entries(self, team):
        env = request.env
        labels = {
            'set': env._("Posted"),
            'edit': env._("Edited"),
            'dismiss': env._("Archived"),
            'restore': env._("Restored"),
        }
        entries = []
        for row in team.note_history_ids:
            tone, state = self.SC_ANNOUNCEMENT_ACTIONS.get(row.action, ('ghost', None))
            entries.append(self._sc_history_entry(
                row.note_datetime, row.author_id.name, row.body,
                action=labels.get(row.action, row.action), tone=tone,
                state=state or ('' if (row.body or '').strip() else 'cleared')))
        return entries

    @http.route(['/my/team/<int:team_id>/announcement/history'],
                type='http', auth='user', website=True, methods=['GET'])
    def portal_team_announcement_history(self, team_id, **kw):
        """Task 1581: the team announcement history sheet's body, fetched on
        EVERY open (a change made on the page shows without a reload). Same
        gate as the team page (its staff; clinic administrators)."""
        try:
            team = self._check_team_access(team_id)
        except MissingError:
            return request.not_found()
        except AccessError as error:
            return self._forbidden(error)
        return request.render('bemade_sports_clinic.sc_announcement_history_fragment', {
            'entries': self._sc_announcement_history_entries(team),
        })

    @http.route(['/my/team/<int:team_id>/player/add'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_add_player_modal_submit(self, team_id, **post):
        """Handle modal submission to link existing or create a new player.
        Only treatment professionals (and admins) can directly add/link.
        Coaches must use the request route.
        """
        # Task 1639: the identity guard for internal users too.
        request.update_context(sc_identity_guard=True)
        try:
            team = self._check_team_access(team_id)

            # Enforce role: only treatment professionals/admin can add
            if not self._is_tp_or_system():
                raise AccessError(_("You don't have permission to add players. You may submit a request instead."))

            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            dob = (post.get('date_of_birth') or '').strip()

            # Task 640: route is restricted to TPs/admins (checked above), who may
            # link ANY patient - including unteamed ones hidden by per-record ir.rules.
            # sudo() so the lookup AND the team_ids write below succeed for a patient
            # the portal user cannot yet read. Adding to a team they staff is the
            # whole point of the feature; full record access remains rule-gated.
            Patient = request.env['sports.patient'].sudo()
            existing = Patient.browse([])
            # Parse existing_id from POST if present (link flow)
            existing_id_str = post.get('existing_id')
            existing_id = int(existing_id_str) if (existing_id_str and str(existing_id_str).isdigit()) else False

            # Owner review 2026-10-11: the app shell's inline « Add a player »
            # links a chosen result (existing_id) or, with force_new, creates
            # exactly the typed player (no fuzzy re-match), then lands on the
            # Players tab / the new player's page.
            sc_inline = bool(post.get('sc_inline'))
            force_new = sc_inline and bool(post.get('force_new'))
            if force_new and not (first_name and last_name):
                raise UserError(_('First name and last name are required'))
            # Only require basic identity fields when creating/searching, not when linking an explicit existing_id
            if not existing_id and not (first_name or last_name):
                raise UserError(_('Provide at least a first or last name'))
            if existing_id:
                existing = Patient.with_context(active_test=False).browse(existing_id).exists()
            elif force_new:
                existing = Patient.browse([])
            else:
                # Try to find existing by name + optional dob (allow partials on whichever provided)
                like_first = f"%{first_name}%" if first_name else "%"
                like_last = f"%{last_name}%" if last_name else "%"
                domain = [
                    ('first_name', 'ilike', like_first),
                    ('last_name', 'ilike', like_last),
                ]
                if dob:
                    domain.append(('date_of_birth', '=', dob))
                existing = Patient.search(domain + [('active', '=', True)], limit=1)
                if not existing:
                    existing = Patient.with_context(active_test=False).search(domain + [('active', '=', False)], limit=1)

            if existing:
                action_taken = []
                if not existing.active:
                    existing.write({'active': True})
                    action_taken.append('reactivated')
                if team not in existing.team_ids:
                    existing.write({'team_ids': [(4, team.id)]})
                    action_taken.append('added to team')

                if sc_inline:
                    success = 'player_reactivated' if 'reactivated' in action_taken else 'player_added_to_team'
                    return request.redirect(f"/my/team?team_id={team.id}&tab=players&success={success}")
                request.session['notification'] = {
                    'type': 'success',
                    'title': _('Player Linked'),
                    'message': _('Existing player %s has been %s.') % (existing.name, ', '.join(action_taken) or _('linked')),
                    'sticky': False,
                }
                return request.redirect(f"/my/team/{team.id}")

            # Create new patient (minimal data)
            vals = {
                'first_name': first_name,
                'last_name': last_name,
                'team_ids': [(4, team.id)],
            }
            if dob:
                vals['date_of_birth'] = dob
            # Pass through status fields (route already restricts to TP/admin)
            if post.get('match_status'):
                vals['match_status'] = post.get('match_status')
            if post.get('practice_status'):
                vals['practice_status'] = post.get('practice_status')

            # Task 1600: a refused create leaves no orphan contact behind.
            with request.env.cr.savepoint():
                patient = request.env['sports.patient']._create_portal_patient(vals)
            if sc_inline:
                return request.redirect(
                    f"/my/player?player_id={patient.id}&team_id={team.id}&tab=info")

            request.session['notification'] = {
                'type': 'success',
                'title': _('Player Created'),
                'message': _('%s has been created and added to the team.') % patient.name,
                'sticky': False,
            }
            # Redirect to edit page with return_url back to team page for two-stage add flow
            edit_url = f"/my/player/edit?patient_id={patient.id}&return_url=/my/team/{team.id}"
            return request.redirect(edit_url)

        except (AccessError, UserError, ValidationError) as e:
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Add Player Failed'),
                'message': self._user_error_text(e, 'team'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
        except Exception as e:
            _logger.exception('Error adding player via modal')
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Add Player Failed'),
                'message': _('An unexpected error occurred.'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")

    @http.route(['/my/player/<int:player_id>/add_to_team'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_add_player_to_team(self, player_id, **post):
        """Link an out-of-reach player (surfaced by the broadened /my/players
        search, task 1225) to one of the current user's staffed teams.

        Security:
        - Restricted to treatment professionals / admins, mirroring the other
          direct add/link routes (coaches keep the request-based flow).
        - The posted team_id is NEVER trusted: it must be a team the user
          actually staffs (or the user is a system admin). Defense in depth, as
          in the create/link flows.
        - sudo() is required because the player may be hidden from the user's
          per-record ir.rules until the team link exists; only then does
          _check_access_to_patient grant the user full record access.
        """
        # Only ever redirect to a same-site, absolute path (the shared
        # validator, task 1579: no scheme, '//host', backslash or control
        # character — no open redirect).
        return_url = self._safe_return_url(post.get('return_url'), '/my/players')

        user = request.env.user
        is_tp_admin = self._is_tp_or_system()
        if not is_tp_admin:
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Access Denied'),
                'message': _("You don't have permission to add players to a team."),
                'sticky': False,
            }
            return request.redirect(return_url)

        try:
            team_id = int(post.get('team_id') or 0)
        except (TypeError, ValueError):
            team_id = 0

        staff_team_ids = set(user.partner_id.team_staff_rel_ids.mapped('team_id.id'))
        # Task 1577: a clinic admin (like a system admin) may add to any team.
        if not team_id or (not self._is_clinic_admin() and team_id not in staff_team_ids):
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Access Denied'),
                'message': _('You can only add players to a team you staff.'),
                'sticky': False,
            }
            return request.redirect(return_url)

        # sudo: see docstring.
        player = request.env['sports.patient'].sudo().browse(player_id).exists()
        team = request.env['sports.team'].sudo().browse(team_id).exists()
        if not player or not team:
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Error'),
                'message': _('Player or team not found.'),
                'sticky': False,
            }
            return request.redirect(return_url)

        if team not in player.team_ids:
            player.write({'team_ids': [fields.Command.link(team.id)]})

        request.session['notification'] = {
            'type': 'success',
            'title': _('Player Added'),
            'message': _('%s has been added to %s.') % (player.name, team.name),
            'sticky': False,
        }
        return request.redirect(return_url)

    @http.route(['/my/team/<int:team_id>/player/request_add'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_request_player_add(self, team_id, **post):
        """Coaches submit a request to add a player. Creates a mail.activity assigned to head therapist or fallback admin."""
        try:
            team = self._check_team_access(team_id, check_staff=True)

            # Only non-therapists need this route; therapists should use direct add
            if self._is_tp_or_system():
                raise AccessError(_('You can add players directly.'))

            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            dob = (post.get('date_of_birth') or '').strip()
            reason = (post.get('reason') or '').strip()

            if not first_name or not last_name:
                raise UserError(_('First name and last name are required'))
            # Require DOB and validate format for better triage by therapists
            if not dob:
                raise UserError(_('Date of birth is required'))
            try:
                # Validate date format (YYYY-MM-DD); will raise if invalid
                fields.Date.to_date(dob)
            except Exception:
                raise UserError(_('Please enter a valid Date of Birth (YYYY-MM-DD).'))

            # Find head therapist (reuse model helper on team if available)
            # Fallback to admin if none
            head_user = False
            if hasattr(team, 'head_therapist_id') and team.head_therapist_id:
                head_user = team.head_therapist_id.user_ids[:1]
            if not head_user:
                head_user = request.env.ref('base.user_admin', raise_if_not_found=False)

            # In Odoo 18, mail.activity requires res_model_id (m2o), not res_model (char)
            # Portal users typically cannot read ir.model; use sudo safely.
            model_rec = request.env['ir.model'].sudo().search([('model', '=', 'sports.team')], limit=1)
            if not model_rec:
                raise UserError(_('Internal error: target model not found. Please contact an administrator.'))
            model_id = model_rec.id
            activity_vals = {
                'res_model_id': model_id,
                'res_id': team.id,
                'summary': _('Coach requests player addition'),
                'note': _('Requested player: %s %s%s\nReason: %s') % (
                    first_name,
                    last_name,
                    (f" (DOB: {dob})" if dob else ''),
                    (reason or _('No reason provided')),
                ),
            }
            if head_user:
                activity_vals['user_id'] = head_user.id

            # Ensure activity is created as a To Do
            todo_type = request.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            if todo_type:
                activity_vals['activity_type_id'] = todo_type.id

            request.env['mail.activity'].sudo().create(activity_vals)

            request.session['notification'] = {
                'type': 'success',
                'title': _('Request Submitted'),
                'message': _('Your request to add a player has been sent to the head therapist.'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team.id}")

        except (AccessError, UserError, ValidationError) as e:
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Request Failed'),
                'message': self._user_error_text(e, 'team'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
        except Exception as e:
            _logger.exception('Error requesting player addition')
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Request Failed'),
                'message': _('An unexpected error occurred.'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
