"""Task 1624 — the app dashboard (``/my/home``): the clinic's widgets.

Task 5202 (kit P7): the page (``/my/home``, ``pk_dash_home`` in
``sc_app_home``), the frame of each section and the « Configurer » sheet
(``/my/app/dashboard/configure`` and its POST routes) are
bemade_portal_kit_dashboard's (``PortalKitDashboard``); the registry, the
layout and the scope are ``portal.kit.dashboard`` (``models/sc_dashboard.py``
plugs the clinic in). This controller brings, through the kit's hooks:

* ``_sc_dash_render``: the clinic's home page (``sc_app_home``, drawn
  with the clinic's shell values); task 5391: the clinic app's
  ``home_render`` (``portal.kit._pk_apps``), called by the kit's ``home()``;
* ``_pk_dash_context``: what the clinic's builders share (labels, the
  recent-changes sets per scope, the player-card scopes…), in the clinic's
  app only (as ``_pk_dash_page_values``);
* the builders ``_sc_dw_<key>(instance, teams, ctx)``: the widgets' rows
  with the app's EXISTING row builders — the player rows of the team page
  (``_sc_player_row`` + ``_sc_player_row_extras``: the coach / therapist
  medical rules, the lazy details), the event rows, the announcement's
  compact layout — once per widget over the scope's teams, never per team;
* ``_pk_dash_page_values``: the page parts — the « À faire » activity
  cards' sheets (once per page) and the kept player cards of a fragment
  refresh (task 1749).

« Suivre / Ne plus suivre » (``/my/player/<id>/follow``) stays here.
"""
import re

from odoo import fields, http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.tools import format_date, format_datetime, html2plaintext

from odoo.addons.bemade_portal_kit.controllers.pk_app import PortalKitApp
from odoo.addons.bemade_portal_kit.tools import pk_field_props
from odoo.addons.bemade_portal_kit_dashboard.controllers.pk_dashboard import PK_DASH_ROWS_SHOWN

from ..models.sc_app_nav import SC_APP
from .task_management_portal import TaskManagementPortal
from .team_management_portal import TeamManagementPortal

HOME_RETURN = 'return_url=%2Fmy%2Fhome'
# Rows / cards shown before « See the N others » (the rest folded): the
# player lists, the events and each « À faire » line's cards (the kit's).
ROWS_SHOWN = PK_DASH_ROWS_SHOWN
# Task 1749: a player card's face fragment (sc_player_row).
DASH_ROW_KEY_RE = re.compile(r'^sports\.patient:(\d+):row-([\w-]+)$')


class AppDashboardPortal(TeamManagementPortal, TaskManagementPortal):

    # ------------------------------------------------------------------
    # The dashboard's page (the kit's hooks; /my/home, PortalKitDashboard)
    # ------------------------------------------------------------------
    def _sc_dash_render(self, values):
        """The clinic's home (``sc_app_home``) with the clinic's shell
        values, as before task 5202."""
        return self._sc_shell_response('bemade_sports_clinic.sc_app_home',
                                       self._sc_app_values(values, 'sc_app_home'))

    def _pk_dash_context(self, Dash, viewer):
        ctx = super()._pk_dash_context(Dash, viewer)
        if viewer.get('app') != SC_APP:
            return ctx
        env = request.env
        ctx.update({
            'changes': {},
            'stage_labels': dict(
                env['sports.patient']._fields['stage']._description_selection(env)),
            'labels': env['sports.patient']._sc_status_labels(),
            'status_edit': self._sc_status_editable(),
            'kinds': dict(env['sports.event']._fields['event_type']._description_selection(env)),
            'tz': env.user.tz or env.context.get('tz'),
            # Review round 1: page-level parts a widget asks for (the
            # activity cards' sheets, once per page).
            'activity_sheets': False,
            # Task 1749: the player-card scopes of the page — {row_scope:
            # {'teams', 'ids' (the players listed), 'changed'}}.
            'row_scopes': {},
        })
        return ctx

    def _pk_dash_page_values(self, values, ctx):
        values = super()._pk_dash_page_values(values, ctx)
        if ctx['viewer'].get('app') != SC_APP:
            return values
        env = request.env
        values.update({
            'page_name': 'home',
            # Review round 1: the injury cards of « À faire » (as on the
            # player page / clinic dossier).
            'sc_is_tp_view': self._sc_injury_tp_view(ctx['viewer']['is_tp']),
            'sc_dash_activity_sheets': ctx['activity_sheets'],
            'today_date': fields.Date.context_today(env.user),
        })
        values.update(self._sc_injury_card_options())
        values['sc_dash_kept_rows'] = self._sc_dash_kept_rows(ctx)
        if ctx['activity_sheets']:
            values.update({
                'sc_dash_available_users': self._activity_assignable_users_for(env.user),
                'sc_dash_today': fields.Date.to_string(values['today_date']),
            })
        return values

    def _sc_dash_scope_rows(self, ctx, row_scope, teams, rows, changed=False):
        """Task 1749: note the player cards a section lists under
        ``row_scope`` (see ``_sc_dash_kept_rows``)."""
        ctx['row_scopes'][row_scope] = {
            'teams': teams or request.env['sports.team'],
            'ids': {row['id'] for row in rows},
            'changed': changed,
        }
        return rows

    def _sc_dash_kept_rows(self, ctx):
        """Task 1749: the player cards a FRAGMENT request asks for that the
        fresh render no longer lists in their section — a status change
        takes the player out of it (« Match : Oui » leaves « Retours en
        retard »; any change makes a recent change, out of « À
        surveiller »). The page keeps such a card where it is until the
        next visit (data-pk-fragment-keep, #1634); rendered here with its
        own scope, it is refreshed in place instead of staying stale.
        Never on a full page render; only players the viewer may read, on
        the section's teams.

        ``[{'scope', 'row'}]`` (sc_app_home, a hidden holder)."""
        keys = PortalKitApp._pk_fragment_keys()
        if not keys:
            return []
        wanted = {}
        for key in keys:
            match = DASH_ROW_KEY_RE.match(key)
            if not match:
                continue
            pid, scope = int(match.group(1)), match.group(2)
            spec = ctx['row_scopes'].get(scope)
            if spec and pid not in spec['ids']:
                wanted.setdefault(scope, []).append(pid)
        kept = []
        Patient = request.env['sports.patient']
        for scope, pids in wanted.items():
            spec = ctx['row_scopes'][scope]
            players = Patient.browse(pids).exists()._filtered_access('read').filtered(
                lambda p: p.sudo().team_ids & spec['teams'])
            for row in self._sc_dash_player_rows(players, spec['teams'], ctx, changed=spec['changed']):
                kept.append({'scope': scope, 'row': row})
        return kept

    @staticmethod
    def _sc_dash_explicit(instance):
        return request.env['portal.kit.dashboard']._pk_dash_explicit(instance['settings'])

    # -- player rows (the team page's builders, once per widget) ------------
    def _sc_dash_player_rows(self, players, teams, ctx, changed=False):
        if not players:
            return []
        extras = self._sc_player_row_extras(
            players, team_links=True, team=None, status_edit=ctx['status_edit'],
            labels=ctx['labels'])
        scope_ids = set(teams.ids)
        universe_ids = set(ctx['universe'].ids)
        rows = []
        for player in players:
            player_teams = player.sudo().team_ids
            team = (player_teams.filtered(lambda t: t.id in scope_ids)[:1]
                    or player_teams.filtered(lambda t: t.id in universe_ids)[:1])
            row = self._sc_player_row(player, team.with_env(request.env), ctx['stage_labels'],
                                      with_position=False, extras=extras)
            if not team:
                # A followed player off my teams (a therapist reads them).
                row['url'] = '/my/player?player_id=%s' % player.id
            if changed:
                row['changed'] = True
                # Task 1626: the change detail, not the plain row detail.
                row['detail_url'] = '/my/player/%s/recent-changes?detail=1&team_id=%s' % (
                    player.id, team.id)
            rows.append(row)
        return rows

    def _sc_dash_changes(self, teams, ctx):
        """The recent-changes set of a scope, computed once per scope for
        the whole page (« Joueurs à surveiller » excludes it)."""
        key = tuple(sorted(teams.ids))
        if key not in ctx['changes']:
            ctx['changes'][key] = request.env['portal.kit.dashboard']._sc_data_changes(
                teams, ctx['viewer'])
        return ctx['changes'][key]

    def _sc_dash_span(self, start, end, ctx):
        """« ven. 31 oct. · 18:00 – 20:00 » (the event page's format)."""
        env = request.env
        start = format_datetime(env, start, tz=ctx['tz'], dt_format='EEE d MMM · HH:mm') if start else ''
        end = format_datetime(env, end, tz=ctx['tz'], dt_format='HH:mm') if end else ''
        return ' – '.join(part for part in (start, end) if part)

    def _sc_dash_event_row(self, event, ctx, fmt='EEE d MMM · HH:mm'):
        env = request.env
        if event.event_type == 'clinic' and ctx['viewer']['is_tp']:
            url = '/my/clinic/%s' % event.id
        else:
            url = '/my/event/%s?%s' % (event.id, HOME_RETURN)
        # sudo: the event itself is read as the viewer (the search); its
        # venue / teams / staff names, as on the event page.
        sudo = event.sudo()
        return {
            'id': event.id,
            'when': format_datetime(env, event.date_start, tz=ctx['tz'], dt_format=fmt),
            'kind': ctx['kinds'].get(event.event_type, ''),
            'name': event.name or '',
            'venue': sudo.venue_id.name or '',
            'teams': ', '.join(sudo.team_ids.mapped('name')),
            'url': url,
            # Review round 1 (owner 2026-10-29): the « Details » fold-out.
            'details': {
                'when': self._sc_dash_span(sudo.date_start, sudo.date_end, ctx),
                # The coverage time is a therapist field (as on the event page).
                'coverage': (self._sc_dash_span(sudo.therapist_start, sudo.therapist_end, ctx)
                             if ctx['viewer']['is_tp'] else ''),
                'staff': ', '.join(sudo.assigned_staff_ids.mapped('name')),
                'description': html2plaintext(sudo.description or '').strip(),
            },
        }

    # -- the widgets (portal.kit.dashboard._pk_widgets 'builder') --------
    def _sc_dw_today(self, instance, teams, ctx):
        env = request.env
        events = env['portal.kit.dashboard']._sc_data_today(ctx['viewer'])
        values = {
            'rows': [self._sc_dash_event_row(event, ctx, fmt='HH:mm') for event in events],
            'show_clinics': False,
        }
        if (env['portal.kit.dashboard']._pk_dash_can('home.clinic_teaser', ctx['viewer'])
                and env['sports.event'].has_access('read')):
            values.update(show_clinics=True, clinics_today=self._sc_clinics_today_count())
        return values

    def _sc_dw_todo(self, instance, teams, ctx):
        """« À faire »: one line per kind; review round 1 (owner 2026-10-29):
        each line folds out inline into its real cards — the activity cards
        of the Activités page (their sheets once on the page), the injury
        cards of the player page, the player cards."""
        env = request.env
        Dash = env['portal.kit.dashboard']
        kinds = [kind for kind in instance['settings'].get('kinds') or ()
                 if kind in Dash._sc_todo_kinds(ctx['viewer'])]
        scope = 'dash-%s' % instance['id']
        lines = []
        if 'activities' in kinds and env['mail.activity'].has_access('read'):
            today = fields.Date.context_today(env.user)
            activities = env['mail.activity'].search(
                self._sc_my_activities_domain([('date_deadline', '<=', today)]),
                order='date_deadline asc, id asc')
            overdue = activities.filtered(lambda a: a.date_deadline < today)
            due_today = activities - overdue
            if overdue:
                lines.append({'kind': 'activities_overdue', 'tone': 'red',
                              'label': env._("Overdue activities"), 'card': 'activity',
                              'url': '/my/activities?tab=overdue', 'cards': overdue})
            if due_today:
                lines.append({'kind': 'activities_today', 'tone': 'secondary',
                              'label': env._("Activities due today"), 'card': 'activity',
                              'url': '/my/activities?tab=today', 'cards': due_today})
            if activities:
                ctx['activity_sheets'] = True
        data = Dash._sc_data_todo(teams, kinds, ctx['viewer'])
        if data.get('verify'):
            injuries = data['verify']
            tp_view = self._sc_injury_tp_view(ctx['viewer']['is_tp'])
            documents = self._sc_injury_card_documents(injuries)
            lines.append({
                'kind': 'verify', 'tone': 'yellow', 'label': env._("Injuries to verify"),
                'card': 'injury', 'url': False,
                'cards': [self._sc_dash_injury_player_head(self._sc_injury_card_row(
                    injury, '', ctx['viewer']['is_tp'], tp_view, documents=documents), ctx)
                    for injury in injuries],
            })
        if data.get('removals'):
            players = data['removals']
            removal_teams = players.sudo().pending_removal_team_id.with_env(env)
            lines.append({
                'kind': 'removals', 'tone': 'ghost', 'label': env._("Removal requests"),
                'card': 'player', 'url': False,
                'cards': self._sc_dash_scope_rows(
                    ctx, '%s-removals' % scope, removal_teams,
                    self._sc_dash_player_rows(players, removal_teams, ctx)),
            })
        if data.get('returns'):
            cards = self._sc_dash_scope_rows(
                ctx, '%s-returns' % scope, teams,
                self._sc_dash_player_rows(data['returns'], teams, ctx))
            self._sc_dash_return_quick_edit(cards, data['returns'], '%s-returns' % scope)
            lines.append({
                'kind': 'returns', 'tone': 'orange', 'label': env._("Overdue returns"),
                'card': 'player', 'url': False, 'cards': cards,
            })
        for line in lines:
            line['count'] = len(line['cards'])
            line['row_scope'] = '%s-%s' % (scope, line['kind'])
            line['more_label'] = (
                env._("See the %(count)s others", count=line['count'] - ROWS_SHOWN)
                if line['count'] > ROWS_SHOWN else '')
        return {'lines': lines, 'card_id_prefix': '%s-injury-' % scope}

    def _sc_dash_injury_player_head(self, row, ctx):
        """Task 1748: an injury card of « À faire » is shown away from its
        player's page — it gets a header line: the player (« #12 Last,
        First », a link to the player page's Injuries tab with THIS injury
        unfolded, the team context kept) and their teams (the viewer's
        universe only). The player page and the clinic dossier show the
        player already: no header there (no ``player_head``)."""
        injury = row['injury']
        player = injury.sudo().patient_id
        universe_ids = set(ctx['universe'].ids)
        teams = player.team_ids.filtered(lambda t: t.id in universe_ids)
        row['player_head'] = {
            'id': player.id,
            'name': player._portal_list_name(),
            'teams': ' · '.join(teams.mapped('name')),
            'url': self._sc_injury_card_url(injury, team_id=teams[:1].id),
        }
        return row

    def _sc_dash_return_quick_edit(self, cards, players, row_scope):
        """Review round 2 (owner 2026-10-29): each « Retours dépassés » card
        gets the player header's « Retour prévu » autosave field — the same
        save route, field rules (therapists: the save specs) and #1727
        « not in the past » rule (``min`` = today; the model refuses a past
        date, shown inline). The line is therapist-only already; a player I
        cannot write gets no field."""
        env = request.env
        today = fields.Date.to_string(fields.Date.context_today(env.user))
        label = env._("Predicted return")
        writable = {player.id: player for player in players._filtered_access('write')}
        for card in cards:
            player = writable.get(card['id'])
            if not player:
                continue
            card['return_edit_props'] = pk_field_props(
                player, 'predicted_return_date', label, 'date', clearable=True, min=today,
                inputId='sc_%s_return_%s' % (row_scope.replace('-', '_'), player.id))

    def _sc_dw_recent_changes(self, instance, teams, ctx):
        env = request.env
        players = self._sc_dash_changes(teams, ctx) if teams else env['sports.patient']
        return {
            'rows': self._sc_dash_scope_rows(
                ctx, 'dash-%s' % instance['id'], teams,
                self._sc_dash_player_rows(players, teams, ctx, changed=True), changed=True),
            'window_label': env._("(last %(hours)s h)",
                                  hours=env['sports.patient']._dashboard_window_hours()),
            # One team in scope: its digest list (the team page's « History »).
            'history_url': ('/my/team/%s/digest-history' % teams.id) if len(teams) == 1 else False,
        }

    def _sc_dw_watch(self, instance, teams, ctx):
        env = request.env
        rows = []
        if teams:
            changed = self._sc_dash_changes(teams, ctx)
            players = env['portal.kit.dashboard']._sc_data_watch(
                teams, instance['settings'].get('level'), changed)
            rows = self._sc_dash_player_rows(players, teams, ctx)
        self._sc_dash_scope_rows(ctx, 'dash-%s' % instance['id'], teams, rows)
        return {'rows': rows}

    def _sc_dw_announcements(self, instance, teams, ctx):
        env = request.env
        items = []
        for team in env['portal.kit.dashboard']._sc_data_announcements(teams or env['sports.team']):
            items.append({
                'team_id': team.id,
                'team': team.name or '',
                'url': '/my/team?team_id=%s' % team.id,
                'text': team.announcement,
                'until': (env._("Until %(date)s", date=format_date(env, team.announcement_deadline))
                          if team.announcement_deadline else ''),
            })
        return {'items': items}

    def _sc_dw_indicators(self, instance, teams, ctx):
        counts = request.env['portal.kit.dashboard']._sc_data_indicators(
            teams or request.env['sports.team'])
        return {'injured': counts['no_play'], 'returning': counts['practice_ok'],
                'available': counts['healthy']}

    def _sc_dw_coverage(self, instance, teams, ctx):
        env = request.env
        days = instance['settings'].get('days') or env['sports.team']._dashboard_upcoming_events_days()
        explicit = self._sc_dash_explicit(instance)
        events = env['portal.kit.dashboard']._sc_data_coverage(teams, days, explicit, ctx['viewer'])
        return {
            # A therapist's assigned events do not need a staffed team.
            'no_scope': not teams and (explicit or not ctx['viewer']['is_tp']),
            'rows': [self._sc_dash_event_row(event, ctx) for event in events],
            'window_label': env._("(next %(days)s days)", days=days),
            'empty_label': (
                env._("No upcoming coverage in the next %(days)s days.", days=days)
                if ctx['viewer']['is_tp']
                else env._("No upcoming events in the next %(days)s days.", days=days)),
            'calendar_url': '/my/events?%s' % HOME_RETURN,
        }

    def _sc_dw_followed(self, instance, teams, ctx):
        """« Joueurs que je suis » (review round 1): my followed players,
        the full expandable cards; the « Portée » filters them."""
        explicit = self._sc_dash_explicit(instance)
        players = request.env['portal.kit.dashboard']._sc_data_followed(teams, explicit)
        rows = self._sc_dash_player_rows(players, teams, ctx)
        return {
            # Nothing chosen = all my followed players, staffed team or not.
            'no_scope': bool(explicit and not teams),
            'rows': rows,
            # Review round 2 (owner 2026-10-29): a LIST read fragment — a
            # follow / unfollow on the page refreshes every instance (each
            # with its own scope): cards added / dropped, count, empty state.
            'fragment_key': 'pk.dashboard:followed:%s' % instance['id'],
            'count_label': '(%s)' % len(rows) if rows else '',
        }

    def _sc_dw_missing_timesheets(self, instance, teams, ctx):
        """« Feuilles de temps manquantes » (review round 1, therapists):
        my past assigned events without a timesheet of mine; « Ajouter ma
        feuille de temps » opens the event page with its add sheet open."""
        env = request.env
        explicit = self._sc_dash_explicit(instance)
        days_back = instance['settings'].get('days_back') or 30
        events = env['portal.kit.dashboard']._sc_data_missing_timesheets(teams, days_back, explicit)
        rows = []
        for event in events:
            row = self._sc_dash_event_row(event, ctx)
            row['add_url'] = '/my/event/%s?add_timesheet=1&%s' % (event.id, HOME_RETURN)
            rows.append(row)
        return {
            'no_scope': bool(explicit and not teams),
            'rows': rows,
            'window_label': env._("(last %(days)s days)", days=days_back),
            # Task 1742: the list of the SAME events (same lower bound).
            'list_url': ('/my/events?view_type=missing_timesheets&assigned_user_id=%s'
                         '&no_default_dates=1&date_from=%s' % (
                             env.uid, fields.Date.to_string(
                                 env['portal.kit.dashboard']._sc_missing_timesheets_since(days_back)[0]))),
        }

    # ------------------------------------------------------------------
    # « Suivre / Ne plus suivre » (review round 1, owner 2026-10-29)
    # ------------------------------------------------------------------
    @http.route(['/my/player/<int:player_id>/follow'], type='http', auth='user', website=True,
                methods=['POST'], multilang=False, sitemap=False)
    def sc_player_follow(self, player_id, follow='1', **post):
        """Follow (``follow=1``) / unfollow (``0``) a player for ME — the
        player cards' and the player page's toggle (sc_follow.js, fetch).
        JSON ``{ok, followed}``; 403 for a role without the toggle or a
        player I cannot read. Without JS: back to where it came from."""
        env = request.env
        wants_json = self._pk_dash_wants_json()
        player = env['sports.patient'].browse(player_id)
        on = str(follow) not in ('0', '', 'false')
        try:
            if not player._sc_follow_allowed():
                raise AccessError(env._("You cannot follow players."))
            if on:
                # An unreadable / unknown player: refused, nothing stored.
                if not env['sports.patient'].search_count([('id', '=', player_id)], limit=1):
                    raise AccessError(env._("You cannot follow this player."))
            player._sc_follow(on)
        except AccessError as error:
            if wants_json:
                return request.make_json_response(
                    {'ok': False, 'error': str(error.args[0] if error.args else error)}, status=403)
            raise
        if wants_json:
            return request.make_json_response({'ok': True, 'followed': on})
        return request.redirect('/my/player?player_id=%s' % player_id)
