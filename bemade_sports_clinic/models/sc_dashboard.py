"""Task 1624 — the app dashboard (``/my/home``): the clinic's widgets.

Task 5202 (kit P7): the engine (registry, per-user layout, zones, v1 → v2,
validation, configure sheet) is bemade_portal_kit_dashboard's
``portal.kit.dashboard``; read its module docstring before adding a widget.
This file plugs the clinic into its hooks:

* ``_pk_widgets``: the clinic's 9 widgets (keys stored in the users'
  layouts — never rename); each names its body template
  (``views/sc_app_dashboard.xml``, ``sc_dw_<key>``), its builder
  (``controllers/app_dashboard.py``, ``_sc_dw_<key>``) and its visibility
  key (``dashboard.<key>``, ``models/sc_app_roles.py``). The order is the
  default layout's (review round 2, owner 2026-10-29: the owner's own
  layout, every section on — left: Aujourd'hui, À faire, Couvertures /
  Événements à venir, Feuilles de temps manquantes; right: Indicateurs,
  Annonces, Joueurs que je suis; bottom: Changements récents, Joueurs à
  surveiller);
* ``_pk_dash_filters``: ``kinds`` (À faire: the 4 kinds of lines, each
  behind its own visibility key), ``level`` (Joueurs à surveiller),
  ``days`` (Couvertures à venir, 0 = the system default) and ``days_back``
  (Feuilles de temps manquantes) — setting names stored in the layouts;
* ``_pk_dash_viewer``: + ``is_tp``, ``is_admin``, ``dash_role``; a coach's
  own wording of a widget (``title_coach``);
* the scope (« Portée »): organisations and / or teams (their union),
  ``scope_org_ids`` / ``scope_team_ids``. Nothing chosen = « Toutes mes
  équipes » = the teams the user staffs (a clinic administrator too: never
  the whole database by default). Whatever is chosen is ALWAYS intersected
  with the teams the user may access (``_sc_scope_universe``: the staffed
  teams; every team for a clinic administrator) — the scope narrows, it
  never widens.

The widgets' data stays here (recordsets, as the viewer).

Task 5391: the widgets, filters and scope fields are the clinic app's
(``SC_APP``); the scope and wording hooks answer for that app only
(``super()`` for any other app of the database).
"""
from datetime import datetime, time, timedelta
from types import MappingProxyType

import pytz

from odoo import api, fields, models
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit_dashboard.models.portal_kit_dashboard import pk_dash_filter, pk_dash_widget

from .sc_app_nav import SC_APP


_lt = LazyTranslate(__name__)

# À faire: the kinds of lines, each behind its own visibility key.
TODO_KINDS = ('activities', 'verify', 'removals', 'returns')
TODO_KIND_KEYS = MappingProxyType({kind: 'dashboard.todo.%s' % kind for kind in TODO_KINDS})
_TODO_KIND_TERMS = (_lt('My activities (overdue and today)'), _lt('Injuries to verify'),
                    _lt('Removal requests'), _lt('Overdue returns'))

# Joueurs à surveiller: red only / red + yellow.
WATCH_LEVELS = ('red_yellow', 'red')
_WATCH_LEVEL_TERMS = (_lt('Red and yellow'), _lt('Red only'))

# Couvertures à venir: the horizon in days (0 = the system default,
# sports.team._dashboard_upcoming_events_days()).
COVERAGE_DAYS = (0, 7, 14, 30)

# Feuilles de temps manquantes: how many days back.
MISSING_DAYS_BACK = (7, 14, 30, 60, 90)


def _widget(key, title, zone, scoped=True, filters=(), defaults=None, title_coach=None):
    return pk_dash_widget(
        key, title, zone, 'bemade_sports_clinic.sc_dw_%s' % key, builder='_sc_dw_%s' % key,
        can='dashboard.%s' % key, scoped=scoped, filters=filters, defaults=defaults, app=SC_APP,
        # Review round 1 (owner 2026-10-29): a coach's own wording (the
        # coverage widget lists their teams' events, not coverage).
        title_coach=title_coach)


class ScDashboard(models.AbstractModel):
    """The clinic's widgets, scope and wording on the kit's dashboard
    engine, as the viewer (``self.env.user``): recordsets read with the
    viewer's own access (record rules apply). The controller turns them
    into rows with the app's existing row builders."""

    _inherit = 'portal.kit.dashboard'

    # ------------------------------------------------------------------
    # Registry, filters, viewer (the kit's hooks)
    # ------------------------------------------------------------------
    @api.model
    def _pk_widgets(self):
        return super()._pk_widgets() + [
            _widget('today', _lt('Today'), 'left', scoped=False),
            _widget('todo', _lt('To do'), 'left', filters=('kinds',)),
            _widget('coverage', _lt('Upcoming coverage'), 'left', filters=('days',),
                    title_coach=_lt('Upcoming events')),
            _widget('missing_timesheets', _lt('Missing timesheets'), 'left', filters=('days_back',)),
            _widget('indicators', _lt('Indicators'), 'right'),
            _widget('announcements', _lt('Announcements'), 'right'),
            _widget('followed', _lt('Players I follow'), 'right'),
            _widget('recent_changes', _lt('Recent changes'), 'bottom'),
            _widget('watch', _lt('Players to watch'), 'bottom', filters=('level',)),
        ]

    @api.model
    def _pk_dash_filters(self):
        env = self.env
        default_days = env['sports.team']._dashboard_upcoming_events_days()
        filters = dict(super()._pk_dash_filters())
        filters.update({
            'kinds': pk_dash_filter('multi', _lt('Show'), zip(TODO_KINDS, _TODO_KIND_TERMS),
                                    default=list(TODO_KINDS), app=SC_APP),
            'level': pk_dash_filter('choice', _lt('Players'), zip(WATCH_LEVELS, _WATCH_LEVEL_TERMS),
                                    default='red_yellow', app=SC_APP),
            'days': pk_dash_filter('int', _lt('Period'), [
                (days, env._("Default (%(days)s days)", days=default_days) if not days
                 else env._("%(days)s days", days=days)) for days in COVERAGE_DAYS], default=0, app=SC_APP),
            'days_back': pk_dash_filter('int', _lt('Days back'), [
                (days, env._("%(days)s days", days=days)) for days in MISSING_DAYS_BACK], default=30,
                app=SC_APP),
        })
        return filters

    @api.model
    def _pk_dash_filter_choices(self, name, viewer):
        choices = super()._pk_dash_filter_choices(name, viewer)
        if name == 'kinds':
            allowed = self._sc_todo_kinds(viewer)
            choices = [choice for choice in choices if choice[0] in allowed]
        return choices

    @api.model
    def _pk_dash_viewer(self):
        viewer = super()._pk_dash_viewer()
        user = self.env.user
        is_system = viewer['is_system']
        is_tp = (user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
                 or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        viewer.update({
            'is_tp': is_tp,
            'is_admin': is_system or user.has_group('bemade_sports_clinic.group_sports_clinic_admin'),
            # The team page's rule (task 1272): the TP rollups for a
            # therapist or a system admin, the coach rollups otherwise.
            'dash_role': 'tp' if (is_tp or is_system) else 'coach',
        })
        return viewer

    @api.model
    def _pk_dash_widget_title(self, spec, viewer=None):
        """A coach (no therapist role) gets ``title_coach`` when the widget
        has one."""
        if spec.get('title_coach') and viewer is not None and not viewer.get('is_tp'):
            return str(spec['title_coach'])
        return super()._pk_dash_widget_title(spec, viewer)

    @api.model
    def _sc_todo_kinds(self, viewer=None):
        viewer = viewer or self._pk_dash_viewer()
        return [kind for kind in TODO_KINDS if self._pk_dash_can(TODO_KIND_KEYS[kind], viewer)]

    @api.model
    def _sc_dash_ours(self, viewer=None):
        """Is the dashboard drawn in the clinic's app?"""
        return self._pk_dash_app(viewer) == SC_APP

    @api.model
    def _pk_dash_intro(self):
        if not self._sc_dash_ours():
            return super()._pk_dash_intro()
        return self.env._("Show, hide, reorder and limit each section to some teams. Changes are saved as you go.")

    # ------------------------------------------------------------------
    # Scope (the kit's hooks)
    # ------------------------------------------------------------------
    @api.model
    def _pk_dash_scope_fields(self):
        return super()._pk_dash_scope_fields() + [
            {'name': 'scope_org_ids', 'label': _lt('Teams of these organizations'),
             'placeholder': _lt('Add an organization…'), 'app': SC_APP},
            {'name': 'scope_team_ids', 'label': _lt('Teams'), 'placeholder': _lt('All my teams'),
             'app': SC_APP},
        ]

    @api.model
    def _pk_dash_scope_universe(self, viewer):
        if not self._sc_dash_ours(viewer):
            return super()._pk_dash_scope_universe(viewer)
        return self._sc_scope_universe(viewer)

    @api.model
    def _pk_dash_scope_allowed(self, universe):
        if not self._sc_dash_ours():
            return super()._pk_dash_scope_allowed(universe)
        return {'scope_team_ids': set(universe.ids), 'scope_org_ids': set(universe.sudo().parent_id.ids)}

    @api.model
    def _pk_dash_scope_options(self, universe):
        if not self._sc_dash_ours():
            return super()._pk_dash_scope_options(universe)
        teams, orgs = self._sc_scope_options(universe=universe)
        return {'scope_team_ids': teams, 'scope_org_ids': orgs}

    @api.model
    def _pk_dash_scope_resolve(self, settings, viewer, universe):
        if not self._sc_dash_ours(viewer):
            return super()._pk_dash_scope_resolve(settings, viewer, universe)
        return self._sc_scope_teams(settings, viewer, universe)

    @api.model
    def _pk_dash_scope_label(self, settings, scope):
        """The section's sub-title: « All my teams », else the chosen
        organisations / teams (two names, then « +N »)."""
        env = self.env
        if not self._sc_dash_ours():
            return super()._pk_dash_scope_label(settings, scope)
        if not self._pk_dash_explicit(settings):
            return env._("All my teams")
        org_ids = set(settings.get('scope_org_ids') or [])
        names = [org.name for org in env['res.partner'].sudo().browse(
            settings.get('scope_org_ids') or []).exists()]
        names += [team.name for team in scope.sudo() if team.parent_id.id not in org_ids]
        if len(names) > 2:
            return env._("%(names)s +%(more)s", names=', '.join(names[:2]), more=len(names) - 2)
        return ', '.join(names)

    @api.model
    def _pk_dash_scope_hint(self):
        if not self._sc_dash_ours():
            return super()._pk_dash_scope_hint()
        return self.env._("Nothing chosen: all your teams.")

    @api.model
    def _pk_dash_scope_refused(self):
        if not self._sc_dash_ours():
            return super()._pk_dash_scope_refused()
        return self.env._("You cannot limit a section to teams or organisations you do not have access to.")

    @api.model
    def _pk_dash_scope_empty_label(self):
        if not self._sc_dash_ours():
            return super()._pk_dash_scope_empty_label()
        return self.env._("No team in this section's scope. Choose teams in « Configure ».")

    @api.model
    def _sc_staffed_teams(self):
        """The teams the user staffs (their staff rows), readable by them."""
        ids = self.env.user.partner_id.sudo().team_staff_rel_ids.team_id.ids
        return self.env['sports.team'].search([('id', 'in', ids)], order='name, id')

    @api.model
    def _sc_scope_universe(self, viewer=None):
        """The teams a scope may name: the staffed teams; EVERY team for a
        clinic administrator (task 1577: they may pick teams they do not
        staff)."""
        viewer = viewer or self._pk_dash_viewer()
        if viewer['is_admin']:
            return self.env['sports.team'].search([], order='name, id')
        return self._sc_staffed_teams()

    @api.model
    def _sc_scope_teams(self, settings, viewer=None, universe=None):
        """The teams of an instance's « Portée »: the chosen teams and the
        teams of the chosen organisations (union); nothing chosen = the
        staffed teams. ALWAYS intersected with ``_sc_scope_universe``."""
        settings = settings or {}
        if universe is None:
            universe = self._sc_scope_universe(viewer)
        team_ids = set(settings.get('scope_team_ids') or ())
        org_ids = set(settings.get('scope_org_ids') or ())
        if not team_ids and not org_ids:
            staffed = set(self.env.user.partner_id.sudo().team_staff_rel_ids.team_id.ids)
            return universe.filtered(lambda team: team.id in staffed)
        return universe.filtered(
            lambda team: team.id in team_ids or team.sudo().parent_id.id in org_ids)

    @api.model
    def _sc_scope_options(self, viewer=None, universe=None):
        """``(team options, organisation options)`` for the scope pickers:
        ``[(id, label)]``, a team labelled « Team (Organisation) »."""
        if universe is None:
            universe = self._sc_scope_universe(viewer)
        teams = []
        orgs = {}
        for team in universe.sudo():
            org = team.parent_id
            teams.append((team.id, '%s (%s)' % (team.name, org.name) if org else team.name or ''))
            if org:
                orgs[org.id] = org.name or ''
        org_options = sorted(orgs.items(), key=lambda item: item[1].lower())
        return sorted(teams, key=lambda item: item[1].lower()), org_options

    # ------------------------------------------------------------------
    # Widget data (recordsets, as the viewer; batched over the scope)
    # ------------------------------------------------------------------
    @api.model
    def _sc_today_bounds(self):
        """Today in the user's timezone, as naive-UTC datetimes."""
        user = self.env.user
        tz = pytz.timezone(user.tz or self.env.context.get('tz') or 'UTC')
        day = fields.Datetime.context_timestamp(user, fields.Datetime.now()).date()
        start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC)
        end = tz.localize(datetime.combine(day, time.max)).astimezone(pytz.UTC)
        return start.replace(tzinfo=None), end.replace(tzinfo=None)

    @api.model
    def _sc_my_events_domain(self, viewer=None):
        """The events of « Aujourd'hui » / « Couvertures à venir »: assigned
        to me (a therapist) on ANY team — a coverage of a team I do not
        staff included (owner 2026-10-29; the callers filter by team only
        for a chosen « Portée ») —, my teams' events (a coach). Never
        cancelled. « Me » = every login sharing my partner, as the « missing
        timesheets » predicate (sports.event._sc_missing_timesheet_domain)."""
        viewer = viewer or self._pk_dash_viewer()
        if viewer['is_tp']:
            user = self.env.user
            mine = self.env['res.users'].sudo().search(
                [('partner_id', '=', user.partner_id.id)]).ids or [user.id]
            domain = [('assigned_staff_ids', 'in', mine)]
        else:
            staffed = self.env.user.partner_id.sudo().team_staff_rel_ids.team_id.ids
            domain = [('team_ids', 'in', staffed or [0])]
        return domain + [('state', '!=', 'cancelled')]

    @api.model
    def _sc_data_today(self, viewer=None):
        start, end = self._sc_today_bounds()
        return self.env['sports.event'].search(
            self._sc_my_events_domain(viewer) + [
                ('date_start', '>=', start), ('date_start', '<=', end)],
            order='date_start, id')

    @api.model
    def _sc_data_coverage(self, teams, days, explicit_scope, viewer=None):
        """Upcoming events within ``days``: a therapist's assigned events (of
        the scoped teams when a scope is chosen), a coach's teams' events
        (the scoped ones)."""
        viewer = viewer or self._pk_dash_viewer()
        now = fields.Datetime.now()
        # Today's events belong to « Aujourd'hui »: start after the viewer's
        # today, so an event never shows in both (and the window doesn't depend
        # on the hour of the day).
        _today_start, today_end = self._sc_today_bounds()
        start = max(now, today_end)
        domain = self._sc_my_events_domain(viewer) + [
            ('date_start', '>', start), ('date_start', '<=', now + timedelta(days=days))]
        if explicit_scope or not viewer['is_tp']:
            domain.append(('team_ids', 'in', teams.ids or [0]))
        return self.env['sports.event'].search(domain, order='date_start, id')

    @api.model
    def _sc_scope_players(self, teams):
        return self.env['sports.patient'].search(
            [('team_ids', 'in', teams.ids or [0]), ('active', '=', True)])

    @api.model
    def _sc_data_changes(self, teams, viewer=None):
        """« Changements récents » over the scope: the players with
        something to show in the role's window (the team page's presence
        rule, ONE batched presence over the union), highest score first."""
        viewer = viewer or self._pk_dash_viewer()
        Patient = self.env['sports.patient']
        role = viewer['dash_role']
        cutoff = Patient._dashboard_window_cutoff()
        stamp = 'dashboard_last_activity_%s' % role
        score = 'dashboard_score_%s' % role
        window = Patient.search([
            ('team_ids', 'in', teams.ids or [0]), ('active', '=', True),
            (stamp, '>=', cutoff)])
        if not window:
            return Patient
        presence = Patient._dashboard_card_presence(window, role, cutoff)
        changed = set(presence['players'])
        return window.filtered(lambda p: p.id in changed).sorted(
            key=lambda p: (-(p[score] or 0), p.last_name or '', p.first_name or '', p.id))

    @api.model
    def _sc_data_watch(self, teams, level, changed):
        """« Joueurs à surveiller »: the red (and yellow) players of the scope
        not in the recent-changes set, red first, then by name."""
        stages = ('no_play',) if level == 'red' else ('no_play', 'practice_ok')
        players = self.env['sports.patient'].search([
            ('team_ids', 'in', teams.ids or [0]), ('active', '=', True),
            ('match_status', '=', 'no')])
        return players.filtered(
            lambda p: p.stage in stages and p not in changed
        ).sorted(key=lambda p: (p.sort_order, p.last_name or '', p.first_name or '', p.id))

    @api.model
    def _sc_data_announcements(self, teams):
        """The scoped teams with a standing, non-expired announcement."""
        return teams.filtered(lambda t: t.announcement and not t.announcement_is_expired)

    @api.model
    def _sc_data_indicators(self, teams):
        """Injured / returning / available counts over the scope's players
        (each player once, however many scoped teams they are on)."""
        players = self._sc_scope_players(teams)
        counts = {'no_play': 0, 'practice_ok': 0, 'healthy': 0}
        for player in players:
            if player.stage in counts:
                counts[player.stage] += 1
        return counts

    @api.model
    def _sc_data_todo(self, teams, kinds, viewer=None):
        """« À faire » team lines over the scope (the activities line is the
        controller's: it shares the app bar clock's domain)."""
        viewer = viewer or self._pk_dash_viewer()
        allowed = set(self._sc_todo_kinds(viewer))
        Patient = self.env['sports.patient']
        data = {}
        if 'verify' in kinds and 'verify' in allowed:
            data['verify'] = self.env['sports.patient.injury'].search([
                ('patient_id.team_ids', 'in', teams.ids or [0]),
                ('patient_id.active', '=', True),
                ('stage', '=', 'unverified')], order='create_date desc, id desc')
        if 'removals' in kinds and 'removals' in allowed:
            removable = Patient._sc_teams_may_remove(teams)
            data['removals'] = Patient.search([
                ('pending_removal', '=', True),
                ('pending_removal_team_id', 'in', removable.ids or [0])])
        if 'returns' in kinds and 'returns' in allowed:
            players = Patient.search([
                ('team_ids', 'in', teams.ids or [0]), ('active', '=', True),
                ('match_status', '=', 'no'), ('predicted_return_overdue', '=', True)])
            data['returns'] = players.sorted(
                key=lambda p: (p.predicted_return_date, p.last_name or '', p.id))
        return data

    @api.model
    def _sc_missing_timesheets_since(self, days_back):
        """Task 1742: ``(day, naive-UTC start of that day)`` — the user's
        today minus ``days_back`` days, the lower bound of « Feuilles de temps
        manquantes » (the widget and its « See all » list)."""
        user = self.env.user
        tz = pytz.timezone(user.tz or self.env.context.get('tz') or 'UTC')
        day = fields.Datetime.context_timestamp(user, fields.Datetime.now()).date() - timedelta(days=days_back)
        start = tz.localize(datetime.combine(day, time.min)).astimezone(pytz.UTC)
        return day, start.replace(tzinfo=None)

    @api.model
    def _sc_data_missing_timesheets(self, teams, days_back, explicit_scope):
        """« Feuilles de temps manquantes » (review round 1): my past events
        (started in the last ``days_back`` days) assigned to me with no
        timesheet of mine — the events page's predicate
        (sports.event._sc_missing_timesheet_domain) — never cancelled;
        filtered by team only when a scope is chosen (an assignment can be
        on a team I do not staff, as « Couvertures à venir »). Newest first."""
        Event = self.env['sports.event']
        # Task 1742: started (the shared predicate), since the start of the
        # day ``days_back`` days ago in the user's timezone — the « See all »
        # list (date_from = that day) shows the very same events.
        _day, since = self._sc_missing_timesheets_since(days_back)
        domain = Event._sc_missing_timesheet_domain() + [
            ('state', '!=', 'cancelled'),
            ('date_start', '>=', since),
        ]
        if explicit_scope:
            domain.append(('team_ids', 'in', teams.ids or [0]))
        return Event.search(domain, order='date_start desc, id desc')

    @api.model
    def _sc_data_followed(self, teams, explicit_scope):
        """« Joueurs que je suis » (review round 1): MY followed players I can
        still read (a lost access hides them), active, those of the scoped
        teams when a scope is chosen; by name."""
        ids = self.env.user.sudo().sc_followed_patient_ids.ids
        if not ids:
            return self.env['sports.patient']
        domain = [('id', 'in', ids), ('active', '=', True)]
        if explicit_scope:
            domain.append(('team_ids', 'in', teams.ids or [0]))
        return self.env['sports.patient'].search(domain).sorted(
            key=lambda p: (p.last_name or '', p.first_name or '', p.id))
