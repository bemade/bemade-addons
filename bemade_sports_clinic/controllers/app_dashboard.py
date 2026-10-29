"""Task 1624 — the app dashboard (``/my/home``) and its « Configurer » page.

The registry, the per-user layout, the scope and the widgets' data live in
``models/sc_dashboard.py`` (``sc.dashboard``, as the viewer). This controller
only turns that data into rows with the app's EXISTING row builders — the
player rows of the team page (``_sc_player_row`` + ``_sc_player_row_extras``:
the coach / therapist medical rules, the lazy details), the event rows, the
announcement's compact layout — once per widget over the scope's teams,
never per team.

« Configurer » (``/my/app/dashboard/configure``): one row per instance — its
switch, ▲ / ▼, and its settings (title, « Portée », the widget's filters),
saved as you go (``sc_dashboard_config.js`` posts the instance's form with
fetch; a refusal shows inside it, #1658); « + Ajouter une section »,
« Supprimer » (added instances), « Rétablir par défaut ». Every POST is
validated by ``sc.dashboard`` (strict) — the page offers nothing the server
would not accept, and the server accepts nothing the page did not offer.
"""
import json
from datetime import timedelta
from urllib.parse import quote

from odoo import fields, http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from odoo.tools import format_date, format_datetime, html2plaintext

from ..models import sc_dashboard
from .task_management_portal import TaskManagementPortal
from .team_management_portal import TeamManagementPortal

CONFIGURE_URL = '/my/app/dashboard/configure'
HOME_RETURN = 'return_url=%2Fmy%2Fhome'
# Rows / cards shown before « See the N others » (the rest folded): the
# player lists, the events and each « À faire » line's cards.
ROWS_SHOWN = 8


def _csv_ints(value):
    ids = []
    for part in str(value or '').split(','):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except ValueError:
                raise ValidationError(request.env._("Invalid scope.")) from None
    return ids


class AppDashboardPortal(TeamManagementPortal, TaskManagementPortal):

    # ------------------------------------------------------------------
    # The dashboard's values (/my/home, AppShellPortal.home)
    # ------------------------------------------------------------------
    def _sc_dashboard_values(self):
        env = request.env
        Dash = env['sc.dashboard']
        viewer = Dash._sc_viewer()
        ctx = {
            'viewer': viewer,
            'universe': Dash._sc_scope_universe(viewer),
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
        }
        sections = []
        for instance in Dash._sc_layout(viewer):
            if not instance['enabled']:
                continue
            spec = sc_dashboard.WIDGETS_BY_KEY[instance['widget']]
            teams = None
            if spec['scoped']:
                teams = Dash._sc_scope_teams(instance['settings'], viewer, ctx['universe'])
            values = getattr(self, spec['builder'])(instance, teams, ctx)
            section = {
                'id': instance['id'],
                'widget': spec['key'],
                'template': spec['template'],
                'title': instance['title'] or sc_dashboard.widget_title(spec, viewer),
                'scope_label': self._sc_dash_scope_label(instance, teams) if spec['scoped'] else '',
                'no_scope': bool(spec['scoped'] and not teams),
                'row_scope': 'dash-%s' % instance['id'],
            }
            section.update(values)
            rows = section.get('rows') or []
            section['rows_shown'] = ROWS_SHOWN
            section['more_rows_label'] = (
                env._("See the %(count)s others", count=len(rows) - ROWS_SHOWN)
                if len(rows) > ROWS_SHOWN else '')
            sections.append(section)
        values = {
            'page_name': 'home',
            'sc_dash_sections': sections,
            'sc_dash_configure_url': CONFIGURE_URL,
            # Review round 1: the injury cards of « À faire » (as on the
            # player page / clinic dossier).
            'sc_is_tp_view': self._sc_injury_tp_view(viewer['is_tp']),
            'sc_dash_activity_sheets': ctx['activity_sheets'],
            'today_date': fields.Date.context_today(env.user),
        }
        values.update(self._sc_injury_card_options())
        if ctx['activity_sheets']:
            values.update({
                'sc_dash_available_users': self._activity_assignable_users_for(env.user),
                'sc_dash_today': fields.Date.to_string(values['today_date']),
            })
        return values

    @staticmethod
    def _sc_dash_explicit(instance):
        settings = instance['settings']
        return bool(settings.get('scope_team_ids') or settings.get('scope_org_ids'))

    def _sc_dash_scope_label(self, instance, teams):
        """The section's sub-title: « All my teams », else the chosen
        organisations / teams (two names, then « +N »)."""
        env = request.env
        if not self._sc_dash_explicit(instance):
            return env._("All my teams")
        settings = instance['settings']
        names = [org.name for org in env['res.partner'].sudo().browse(
            settings.get('scope_org_ids') or []).exists()]
        org_ids = set(settings.get('scope_org_ids') or [])
        names += [team.name for team in teams.sudo()
                  if team.parent_id.id not in org_ids]
        if len(names) > 2:
            return env._("%(names)s +%(more)s", names=', '.join(names[:2]), more=len(names) - 2)
        return ', '.join(names)

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
            ctx['changes'][key] = request.env['sc.dashboard']._sc_data_changes(
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

    # -- the widgets (sc_dashboard.WIDGETS 'builder') ---------------------
    def _sc_dw_today(self, instance, teams, ctx):
        env = request.env
        events = env['sc.dashboard']._sc_data_today(ctx['viewer'])
        values = {
            'rows': [self._sc_dash_event_row(event, ctx, fmt='HH:mm') for event in events],
            'show_clinics': False,
        }
        if (env['sc.dashboard']._sc_can('home.clinic_teaser', ctx['viewer'])
                and env['sports.event'].has_access('read')):
            values.update(show_clinics=True, clinics_today=self._sc_clinics_today_count())
        return values

    def _sc_dw_todo(self, instance, teams, ctx):
        """« À faire »: one line per kind; review round 1 (owner 2026-10-29):
        each line folds out inline into its real cards — the activity cards
        of the Activités page (their sheets once on the page), the injury
        cards of the player page, the player cards."""
        env = request.env
        Dash = env['sc.dashboard']
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
                lines.append({'kind': 'activities_today', 'tone': 'mauve',
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
                'cards': [self._sc_injury_card_row(
                    injury, '', ctx['viewer']['is_tp'], tp_view, documents=documents)
                    for injury in injuries],
            })
        if data.get('removals'):
            players = data['removals']
            removal_teams = players.sudo().pending_removal_team_id.with_env(env)
            lines.append({
                'kind': 'removals', 'tone': 'ghost', 'label': env._("Removal requests"),
                'card': 'player', 'url': False,
                'cards': self._sc_dash_player_rows(players, removal_teams, ctx),
            })
        if data.get('returns'):
            lines.append({
                'kind': 'returns', 'tone': 'orange', 'label': env._("Overdue returns"),
                'card': 'player', 'url': False,
                'cards': self._sc_dash_player_rows(data['returns'], teams, ctx),
            })
        for line in lines:
            line['count'] = len(line['cards'])
            line['row_scope'] = '%s-%s' % (scope, line['kind'])
            line['more_label'] = (
                env._("See the %(count)s others", count=line['count'] - ROWS_SHOWN)
                if line['count'] > ROWS_SHOWN else '')
        return {'lines': lines, 'card_id_prefix': '%s-injury-' % scope}

    def _sc_dw_recent_changes(self, instance, teams, ctx):
        env = request.env
        players = self._sc_dash_changes(teams, ctx) if teams else env['sports.patient']
        return {
            'rows': self._sc_dash_player_rows(players, teams, ctx, changed=True),
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
            players = env['sc.dashboard']._sc_data_watch(
                teams, instance['settings'].get('level'), changed)
            rows = self._sc_dash_player_rows(players, teams, ctx)
        return {'rows': rows}

    def _sc_dw_announcements(self, instance, teams, ctx):
        env = request.env
        items = []
        for team in env['sc.dashboard']._sc_data_announcements(teams or env['sports.team']):
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
        counts = request.env['sc.dashboard']._sc_data_indicators(
            teams or request.env['sports.team'])
        return {'injured': counts['no_play'], 'returning': counts['practice_ok'],
                'available': counts['healthy']}

    def _sc_dw_coverage(self, instance, teams, ctx):
        env = request.env
        days = instance['settings'].get('days') or env['sports.team']._dashboard_upcoming_events_days()
        explicit = self._sc_dash_explicit(instance)
        events = env['sc.dashboard']._sc_data_coverage(teams, days, explicit, ctx['viewer'])
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
        players = request.env['sc.dashboard']._sc_data_followed(teams, explicit)
        return {
            # Nothing chosen = all my followed players, staffed team or not.
            'no_scope': bool(explicit and not teams),
            'rows': self._sc_dash_player_rows(players, teams, ctx),
        }

    def _sc_dw_missing_timesheets(self, instance, teams, ctx):
        """« Feuilles de temps manquantes » (review round 1, therapists):
        my past assigned events without a timesheet of mine; « Ajouter ma
        feuille de temps » opens the event page with its add sheet open."""
        env = request.env
        explicit = self._sc_dash_explicit(instance)
        days_back = instance['settings'].get('days_back') or 30
        events = env['sc.dashboard']._sc_data_missing_timesheets(teams, days_back, explicit)
        rows = []
        for event in events:
            row = self._sc_dash_event_row(event, ctx)
            row['add_url'] = '/my/event/%s?add_timesheet=1&%s' % (event.id, HOME_RETURN)
            rows.append(row)
        return {
            'no_scope': bool(explicit and not teams),
            'rows': rows,
            'window_label': env._("(last %(days)s days)", days=days_back),
            'list_url': ('/my/events?view_type=missing_timesheets&assigned_user_id=%s'
                         '&no_default_dates=1' % env.uid),
        }

    # ------------------------------------------------------------------
    # « Configurer »
    # ------------------------------------------------------------------
    @http.route([CONFIGURE_URL], type='http', auth='user', website=True)
    def sc_dashboard_configure(self, **kw):
        if not self._sc_app_shell_active():
            return request.redirect('/my/home')
        env = request.env
        Dash = env['sc.dashboard']
        viewer = Dash._sc_viewer()
        layout = Dash._sc_layout(viewer)
        team_options, org_options = Dash._sc_scope_options(viewer)
        allowed = Dash._sc_widgets(viewer)
        todo_kinds = Dash._sc_todo_kinds(viewer)
        default_days = env['sports.team']._dashboard_upcoming_events_days()
        rows = []
        for index, instance in enumerate(layout):
            spec = sc_dashboard.WIDGETS_BY_KEY[instance['widget']]
            settings = instance['settings']
            row = {
                'id': instance['id'],
                'widget': spec['key'],
                'widget_title': sc_dashboard.widget_title(spec, viewer),
                'title': instance['title'],
                'enabled': instance['enabled'],
                'removable': instance['id'] != spec['key'],
                'first': index == 0,
                'last': index == len(layout) - 1,
                'scoped': spec['scoped'],
                'filters': spec['filters'],
                'settings': settings,
            }
            if spec['scoped']:
                row['team_target'] = 'sc_dash_%s_teams' % instance['id']
                row['org_target'] = 'sc_dash_%s_orgs' % instance['id']
                row['team_csv'] = ','.join(str(i) for i in settings.get('scope_team_ids') or [])
                row['org_csv'] = ','.join(str(i) for i in settings.get('scope_org_ids') or [])
                row['team_props'] = self._sc_form_props(
                    row['team_target'], env._("Teams"), 'tags', row['team_csv'],
                    options=team_options, placeholder=env._("All my teams"))
                row['org_props'] = self._sc_form_props(
                    row['org_target'], env._("Teams of these organizations"), 'tags', row['org_csv'],
                    options=org_options, placeholder=env._("Add an organization…"))
            if 'kinds' in spec['filters']:
                row['kind_choices'] = [
                    (kind, str(sc_dashboard.TODO_KIND_LABELS[kind]), kind in (settings.get('kinds') or ()))
                    for kind in todo_kinds]
            if 'level' in spec['filters']:
                row['level_choices'] = [
                    (level, str(sc_dashboard.WATCH_LEVEL_LABELS[level]), settings.get('level') == level)
                    for level in sc_dashboard.WATCH_LEVELS]
            if 'days' in spec['filters']:
                row['days_choices'] = [
                    (days, env._("Default (%(days)s days)", days=default_days) if not days
                     else env._("%(days)s days", days=days), (settings.get('days') or 0) == days)
                    for days in sc_dashboard.COVERAGE_DAYS]
            if 'days_back' in spec['filters']:
                row['days_back_choices'] = [
                    (days, env._("%(days)s days", days=days), settings.get('days_back') == days)
                    for days in sc_dashboard.MISSING_DAYS_BACK]
            rows.append(row)
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'sc_app_dashboard_configure',
            'sc_dash_rows': rows,
            'sc_dash_add_choices': [(spec['key'], sc_dashboard.widget_title(spec, viewer))
                                    for spec in allowed],
            'sc_dash_error': request.session.pop('sc_dash_error', None),
        })
        return self._sc_shell_response(
            'bemade_sports_clinic.sc_app_dashboard_configure',
            self._sc_app_values(values, 'sc_app_dashboard_configure'))

    @staticmethod
    def _sc_dash_wants_json():
        return request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _sc_dash_done(self, anchor=None, error=None):
        """Answer a « Configurer » POST: JSON for the page's fetch, else
        back to the page (PRG), the refusal shown there."""
        if self._sc_dash_wants_json():
            if error:
                return request.make_json_response({'ok': False, 'error': error}, status=400)
            return request.make_json_response({'ok': True})
        if error:
            request.session['sc_dash_error'] = error
        return request.redirect(CONFIGURE_URL + ('#sc-dash-%s' % anchor if anchor else ''))

    def _sc_dash_post(self, run, anchor=None):
        if not self._sc_app_shell_active():
            return request.redirect('/my/home')
        try:
            result = run(request.env['sc.dashboard'])
        except ValidationError as error:
            return self._sc_dash_done(anchor, error=str(error.args[0] if error.args else error))
        return self._sc_dash_done(result or anchor)

    @http.route([CONFIGURE_URL + '/save'], type='http', auth='user', website=True,
                methods=['POST'])
    def sc_dashboard_configure_save(self, instance_id=None, **post):
        def run(Dash):
            settings = {}
            if 'scope_team_ids' in post:
                settings['scope_team_ids'] = _csv_ints(post.get('scope_team_ids'))
            if 'scope_org_ids' in post:
                settings['scope_org_ids'] = _csv_ints(post.get('scope_org_ids'))
            if post.get('kinds_present'):
                settings['kinds'] = request.httprequest.form.getlist('kinds')
            if 'level' in post:
                settings['level'] = post.get('level')
            if 'days' in post:
                settings['days'] = post.get('days')
            if 'days_back' in post:
                settings['days_back'] = post.get('days_back')
            enabled = None
            if 'enabled' in post:
                enabled = post.get('enabled') not in ('0', '', 'false')
            Dash._sc_layout_update(
                instance_id, enabled=enabled,
                title=post.get('title') if 'title' in post else None,
                settings=settings or None)
        return self._sc_dash_post(run, instance_id)

    @http.route([CONFIGURE_URL + '/move'], type='http', auth='user', website=True,
                methods=['POST'])
    def sc_dashboard_configure_move(self, instance_id=None, step=None, **post):
        return self._sc_dash_post(
            lambda Dash: Dash._sc_layout_move(instance_id, -1 if step == 'up' else 1), instance_id)

    @http.route([CONFIGURE_URL + '/add'], type='http', auth='user', website=True,
                methods=['POST'])
    def sc_dashboard_configure_add(self, widget=None, **post):
        return self._sc_dash_post(lambda Dash: Dash._sc_layout_add(widget))

    @http.route([CONFIGURE_URL + '/remove'], type='http', auth='user', website=True,
                methods=['POST'])
    def sc_dashboard_configure_remove(self, instance_id=None, **post):
        return self._sc_dash_post(lambda Dash: Dash._sc_layout_remove(instance_id))

    @http.route([CONFIGURE_URL + '/reset'], type='http', auth='user', website=True,
                methods=['POST'])
    def sc_dashboard_configure_reset(self, **post):
        def run(Dash):
            Dash._sc_layout_reset()
        return self._sc_dash_post(run)

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
        wants_json = self._sc_dash_wants_json()
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
