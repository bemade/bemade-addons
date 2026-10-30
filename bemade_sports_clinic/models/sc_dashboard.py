"""Task 1624 — the app dashboard (``/my/home``): configurable widget sections.

Read this before adding a dashboard widget.

Widget registry
---------------
``WIDGETS`` is THE list of dashboard widgets. Each entry declares:

* ``key``       stable identifier (stored in the users' layouts — never rename);
* ``title``     the default section title (translatable);
* ``can``       the ``sc_app_roles.VISIBILITY_REGISTRY`` key deciding which
                roles may have it (``sc_can``);
* ``template``  the QWeb template of its body (``views/sc_app_dashboard.xml``);
* ``builder``   the name of the controller method building its render values,
                ``builder(instance, ctx) -> dict`` (``controllers/app_dashboard.py``);
* ``scoped``    it takes the « Portée » filter (organisations / teams);
* ``filters``   its widget-specific settings (``FILTERS``);
* ``defaults``  the default value of each of those settings.

Adding a widget = one ``_widget(...)`` entry here + its template + its
builder. Nothing else.

Per-user layout
---------------
``res.users.sc_dashboard_layout`` (JSON, written by the « Configurer » page
only, through ``sc.dashboard._sc_layout_save``)::

    {"v": 2, "instances": [
        {"id": "watch", "widget": "watch", "zone": "bottom", "enabled": true, "title": "",
         "settings": {"scope_team_ids": [], "scope_org_ids": [], "level": "red_yellow"}},
        {"id": "watch-2", "widget": "watch", "zone": "right", "enabled": true,
         "title": "Joueurs à surveiller — Bourget", "settings": {...}},
        ...]}

* Zones (review round 2, owner 2026-10-29): every instance sits in one of
  three ``ZONES`` — ``left`` / ``right`` (two independent columns side by
  side on a laptop) and ``bottom`` (full width under both). On a phone the
  page reads left, then right, then bottom. The instance list is kept in
  that order (zone, then position in the zone).
* ``v: 1`` layouts (no zones) still load: their instances keep their order,
  the first half (rounded up) goes left, the rest right — the two flowing
  columns they used to fill. The next save writes ``v: 2``.

* Several instances of one widget are allowed, each with its own settings
  and an optional custom title. Every widget keeps its BASE instance (id =
  the widget key): it can be switched off, never removed; the instances
  added with « + Ajouter une section » can be removed.
* A missing / invalid layout (or an unknown ``v``) falls back to the code
  default; unknown widget keys and widgets the user's roles do not allow
  are ignored (forward compatible); a widget added to the registry later
  joins every saved layout at the end.
* A save is validated server-side (``_sc_layout_save``): known widget,
  allowed role, setting values from their choices, scope ids the user may
  use — anything else is REFUSED with a clear message, never silently fixed.

Scope (« Portée »)
------------------
Organisations and / or teams (their union). Nothing chosen = « Toutes mes
équipes » = the teams the user staffs (a clinic administrator too: never the
whole database by default). Whatever is chosen is ALWAYS intersected with the
teams the user may access (``_sc_scope_universe``: the staffed teams; every
team for a clinic administrator) — the scope narrows, it never widens.
"""
import re
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import LazyTranslate

from . import sc_app_roles

_lt = LazyTranslate(__name__)

LAYOUT_VERSION = 2
# The versions a stored layout may have (older ones are migrated on load).
LAYOUT_VERSIONS = (1, 2)
MAX_INSTANCES = 30
TITLE_MAX = 80
_ID_RE = re.compile(r'^[a-z0-9_-]{1,40}$')

# À faire: the kinds of lines, each behind its own visibility key.
TODO_KINDS = ('activities', 'verify', 'removals', 'returns')
TODO_KIND_KEYS = {kind: 'dashboard.todo.%s' % kind for kind in TODO_KINDS}
_TODO_KIND_TERMS = (_lt('My activities (overdue and today)'), _lt('Injuries to verify'),
                    _lt('Removal requests'), _lt('Overdue returns'))
TODO_KIND_LABELS = dict(zip(TODO_KINDS, _TODO_KIND_TERMS))

# Joueurs à surveiller: red only / red + yellow.
WATCH_LEVELS = ('red_yellow', 'red')
_WATCH_LEVEL_TERMS = (_lt('Red and yellow'), _lt('Red only'))
WATCH_LEVEL_LABELS = dict(zip(WATCH_LEVELS, _WATCH_LEVEL_TERMS))

# Couvertures à venir: the horizon in days (0 = the system default,
# sports.team._dashboard_upcoming_events_days()).
COVERAGE_DAYS = (0, 7, 14, 30)

# Feuilles de temps manquantes: how many days back.
MISSING_DAYS_BACK = (7, 14, 30, 60, 90)

# Review round 2 (owner 2026-10-29): the three zones of the page, in their
# phone reading order.
ZONES = ('left', 'right', 'bottom')
_ZONE_TERMS = (_lt('Left'), _lt('Right'), _lt('Bottom'))
ZONE_LABELS = dict(zip(ZONES, _ZONE_TERMS))

# Widget-specific settings: name -> kind ('multi' = a subset of choices,
# 'choice' = one of them).
FILTERS = {
    'kinds': {'type': 'multi', 'choices': TODO_KINDS},
    'level': {'type': 'choice', 'choices': WATCH_LEVELS},
    'days': {'type': 'choice', 'choices': COVERAGE_DAYS},
    'days_back': {'type': 'choice', 'choices': MISSING_DAYS_BACK},
}
# The settings posted / stored as integers.
INT_FILTERS = ('days', 'days_back')


def _widget(key, title, zone, scoped=True, filters=(), defaults=None, title_coach=None):
    return {
        'key': key,
        'title': title,
        # Review round 2: the zone of its base instance in the default layout.
        'zone': zone,
        # Review round 1 (owner 2026-10-29): a coach's own wording (the
        # coverage widget lists their teams' events, not coverage).
        'title_coach': title_coach,
        'can': 'dashboard.%s' % key,
        'template': 'bemade_sports_clinic.sc_dw_%s' % key,
        'builder': '_sc_dw_%s' % key,
        'scoped': scoped,
        'filters': tuple(filters),
        'defaults': dict(defaults or {}),
    }


# The order is the default layout's order, zone by zone. Review round 2
# (owner 2026-10-29): the default = the owner's own layout, every section on
# — left: Aujourd'hui, À faire, Couvertures / Événements à venir, Feuilles
# de temps manquantes; right: Indicateurs, Annonces, Joueurs que je suis;
# bottom (full width): Changements récents, Joueurs à surveiller. A saved
# layout keeps its own order; a widget it does not hold yet joins the end
# of its default zone.
WIDGETS = (
    _widget('today', _lt('Today'), 'left', scoped=False),
    _widget('todo', _lt('To do'), 'left', filters=('kinds',), defaults={'kinds': list(TODO_KINDS)}),
    _widget('coverage', _lt('Upcoming coverage'), 'left', filters=('days',), defaults={'days': 0},
            title_coach=_lt('Upcoming events')),
    _widget('missing_timesheets', _lt('Missing timesheets'), 'left', filters=('days_back',),
            defaults={'days_back': 30}),
    _widget('indicators', _lt('Indicators'), 'right'),
    _widget('announcements', _lt('Announcements'), 'right'),
    _widget('followed', _lt('Players I follow'), 'right'),
    _widget('recent_changes', _lt('Recent changes'), 'bottom'),
    _widget('watch', _lt('Players to watch'), 'bottom', filters=('level',),
            defaults={'level': 'red_yellow'}),
)
WIDGETS_BY_KEY = {spec['key']: spec for spec in WIDGETS}


def widget_title(spec, viewer=None):
    """The widget's default title for this viewer: a coach (no therapist
    role) gets ``title_coach`` when the widget has one."""
    if spec.get('title_coach') and viewer is not None and not viewer['is_tp']:
        return str(spec['title_coach'])
    return str(spec['title'])


class ScDashboard(models.AbstractModel):
    """The dashboard's logic, as the viewer (``self.env.user``): the layout,
    the scope and the data of each widget, as recordsets read with the
    viewer's own access (record rules apply). The controller turns them into
    rows with the app's existing row builders."""

    _name = 'sc.dashboard'
    _description = 'App dashboard (task 1624)'

    # ------------------------------------------------------------------
    # The viewer
    # ------------------------------------------------------------------
    @api.model
    def _sc_viewer(self):
        user = self.env.user
        is_system = user.has_group('base.group_system')
        is_tp = (user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
                 or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional'))
        is_admin = is_system or user.has_group('bemade_sports_clinic.group_sports_clinic_admin')
        return {
            'roles': user._sc_app_roles(),
            'is_system': is_system,
            'is_tp': is_tp,
            'is_admin': is_admin,
            # The team page's rule (task 1272): the TP rollups for a
            # therapist or a system admin, the coach rollups otherwise.
            'dash_role': 'tp' if (is_tp or is_system) else 'coach',
        }

    @api.model
    def _sc_can(self, key, viewer=None):
        viewer = viewer or self._sc_viewer()
        return sc_app_roles.can(key, viewer['roles'], is_system=viewer['is_system'])

    @api.model
    def _sc_widgets(self, viewer=None):
        """The registry entries this user may have, in registry order."""
        viewer = viewer or self._sc_viewer()
        return [spec for spec in WIDGETS if self._sc_can(spec['can'], viewer)]

    @api.model
    def _sc_todo_kinds(self, viewer=None):
        viewer = viewer or self._sc_viewer()
        return [kind for kind in TODO_KINDS if self._sc_can(TODO_KIND_KEYS[kind], viewer)]

    # ------------------------------------------------------------------
    # Scope
    # ------------------------------------------------------------------
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
        viewer = viewer or self._sc_viewer()
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
    def _sc_scope_options(self, viewer=None):
        """``(team options, organisation options)`` for the scope pickers:
        ``[(id, label)]``, a team labelled « Team (Organisation) »."""
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
    # Layout
    # ------------------------------------------------------------------
    @staticmethod
    def _sc_zone_sorted(instances):
        """The instances in page order: zone by zone (``ZONES``), each zone
        in its own order (a stable sort)."""
        return sorted(instances, key=lambda inst: ZONES.index(inst['zone']))

    @api.model
    def _sc_default_instance(self, spec, instance_id=None, zone=None):
        settings = {'scope_team_ids': [], 'scope_org_ids': []} if spec['scoped'] else {}
        for name in spec['filters']:
            default = spec['defaults'].get(name)
            settings[name] = list(default) if isinstance(default, list) else default
        return {
            'id': instance_id or spec['key'],
            'widget': spec['key'],
            'zone': zone or spec['zone'],
            'enabled': True,
            'title': '',
            'settings': settings,
        }

    @api.model
    def _sc_layout_default(self, viewer=None):
        return [self._sc_default_instance(spec) for spec in self._sc_widgets(viewer)]

    @api.model
    def _sc_clean_settings(self, spec, raw, strict, universe_ids=None, org_ids=None):
        """``raw`` settings -> the instance's clean settings. ``strict``
        (a save) raises on any value outside its choices / the user's
        scope; otherwise (a load) such values are dropped."""
        raw = raw if isinstance(raw, dict) else {}
        clean = self._sc_default_instance(spec)['settings']
        if spec['scoped']:
            for name, allowed in (('scope_team_ids', universe_ids), ('scope_org_ids', org_ids)):
                ids = []
                for value in raw.get(name) or []:
                    try:
                        ids.append(int(value))
                    except (TypeError, ValueError):
                        if strict:
                            raise ValidationError(self.env._("Invalid scope."))
                foreign = [i for i in ids if allowed is not None and i not in allowed]
                if foreign and strict:
                    raise ValidationError(self.env._(
                        "You cannot limit a section to teams or organisations you do not have access to."))
                clean[name] = sorted({i for i in ids if i not in foreign})
        for name in spec['filters']:
            if name not in raw:
                continue
            kind = FILTERS[name]
            value = raw[name]
            if kind['type'] == 'multi':
                values = value if isinstance(value, (list, tuple)) else [value]
                bad = [v for v in values if v not in kind['choices']]
                if bad and strict:
                    raise ValidationError(self.env._("Invalid setting."))
                clean[name] = [c for c in kind['choices'] if c in values]
            else:
                if name in INT_FILTERS:
                    try:
                        value = int(value or 0)
                    except (TypeError, ValueError):
                        value = None
                if value not in kind['choices']:
                    if strict:
                        raise ValidationError(self.env._("Invalid setting."))
                    continue
                clean[name] = value
        return clean

    @api.model
    def _sc_normalize(self, raw, strict=False, viewer=None):
        """A stored / posted layout -> the clean ordered instance list for
        this user (see the module docstring for the rules)."""
        viewer = viewer or self._sc_viewer()
        allowed = {spec['key']: spec for spec in self._sc_widgets(viewer)}
        if not (isinstance(raw, dict) and raw.get('v') in LAYOUT_VERSIONS
                and isinstance(raw.get('instances'), list)):
            if strict:
                raise ValidationError(self.env._("Invalid dashboard layout."))
            return self._sc_layout_default(viewer)
        if raw['v'] != LAYOUT_VERSION:
            if strict:
                raise ValidationError(self.env._("Invalid dashboard layout."))
            raw = self._sc_layout_migrate(raw)
        universe = self._sc_scope_universe(viewer)
        universe_ids = set(universe.ids)
        org_ids = set(universe.sudo().parent_id.ids)
        clean, seen = [], set()
        for item in raw['instances']:
            if not isinstance(item, dict):
                if strict:
                    raise ValidationError(self.env._("Invalid dashboard layout."))
                continue
            key = item.get('widget')
            spec = allowed.get(key)
            if spec is None:
                if strict:
                    raise ValidationError(self.env._("This section is not available to you."))
                continue  # unknown (a later version) or not for this role
            instance_id = str(item.get('id') or '')
            if not _ID_RE.match(instance_id) or instance_id in seen:
                if strict:
                    raise ValidationError(self.env._("Invalid dashboard layout."))
                continue
            if not instance_id.startswith(key):
                if strict:
                    raise ValidationError(self.env._("Invalid dashboard layout."))
                continue
            seen.add(instance_id)
            title = item.get('title') or ''
            if not isinstance(title, str):
                title = ''
            zone = item.get('zone')
            if zone not in ZONES:
                if strict:
                    raise ValidationError(self.env._("Invalid dashboard layout."))
                zone = spec['zone']
            clean.append({
                'id': instance_id,
                'widget': key,
                'zone': zone,
                'enabled': bool(item.get('enabled', True)),
                'title': ' '.join(title.split())[:TITLE_MAX],
                'settings': self._sc_clean_settings(
                    spec, item.get('settings'), strict, universe_ids, org_ids),
            })
        if len(clean) > MAX_INSTANCES and strict:
            raise ValidationError(self.env._("Too many sections."))
        # Every widget keeps its base instance (a widget added to the
        # registry later joins the saved layouts at the end of its zone).
        for key, spec in allowed.items():
            if key not in seen:
                clean.append(self._sc_default_instance(spec))
        return self._sc_zone_sorted(clean)

    @api.model
    def _sc_layout_migrate(self, raw):
        """A ``v: 1`` layout (no zones) -> ``v: 2``: the order kept, the first
        half (rounded up) in the left column, the rest in the right one —
        where they flowed in the two automatic columns."""
        items = [dict(item) for item in raw.get('instances') or [] if isinstance(item, dict)]
        half = (len(items) + 1) // 2
        for index, item in enumerate(items):
            item['zone'] = 'left' if index < half else 'right'
        return {'v': LAYOUT_VERSION, 'instances': items}

    @api.model
    def _sc_layout(self, viewer=None):
        return self._sc_normalize(self.env.user.sudo().sc_dashboard_layout, viewer=viewer)

    @api.model
    def _sc_layout_save(self, instances, viewer=None):
        """Validate (strict) and store the user's layout; returns the clean
        instance list. sudo: the field is not self-writable on purpose —
        only this validated path writes it."""
        clean = self._sc_normalize(
            {'v': LAYOUT_VERSION, 'instances': instances}, strict=True, viewer=viewer)
        self.env.user.sudo().sc_dashboard_layout = {'v': LAYOUT_VERSION, 'instances': clean}
        return clean

    @api.model
    def _sc_layout_reset(self):
        self.env.user.sudo().sc_dashboard_layout = False
        return self._sc_layout()

    @api.model
    def _sc_layout_add_zone(self, layout):
        """« Ajouter une section »'s default zone: the shorter of the two
        columns (fewer shown sections; left on a tie)."""
        count = {zone: sum(1 for inst in layout if inst['zone'] == zone and inst['enabled'])
                 for zone in ('left', 'right')}
        return 'right' if count['right'] < count['left'] else 'left'

    @api.model
    def _sc_layout_add(self, widget_key, viewer=None, zone=None):
        """A new instance of ``widget_key`` at the end of ``zone`` (default:
        the shorter column); returns its id."""
        viewer = viewer or self._sc_viewer()
        spec = {s['key']: s for s in self._sc_widgets(viewer)}.get(widget_key)
        if spec is None:
            raise ValidationError(self.env._("This section is not available to you."))
        if zone is not None and zone not in ZONES:
            raise ValidationError(self.env._("Invalid dashboard layout."))
        layout = self._sc_layout(viewer)
        zone = zone or self._sc_layout_add_zone(layout)
        ids = {inst['id'] for inst in layout}
        new_id = None
        for n in range(2, MAX_INSTANCES + 2):
            candidate = '%s-%s' % (widget_key, n)
            if candidate not in ids:
                new_id = candidate
                break
        if new_id is None or len(layout) >= MAX_INSTANCES:
            raise ValidationError(self.env._("Too many sections."))
        layout.append(self._sc_default_instance(spec, new_id, zone=zone))
        self._sc_layout_save(self._sc_zone_sorted(layout), viewer)
        return new_id

    @api.model
    def _sc_layout_remove(self, instance_id, viewer=None):
        layout = self._sc_layout(viewer)
        target = next((inst for inst in layout if inst['id'] == instance_id), None)
        if target is None:
            raise ValidationError(self.env._("This section no longer exists."))
        if target['id'] == target['widget']:
            raise ValidationError(self.env._("This section can be switched off, not removed."))
        self._sc_layout_save([inst for inst in layout if inst['id'] != instance_id], viewer)

    @api.model
    def _sc_layout_move(self, instance_id, step, viewer=None):
        """▲ / ▼: one step up / down WITHIN its zone (no-op at its edge)."""
        layout = self._sc_layout(viewer)
        target = next((inst for inst in layout if inst['id'] == instance_id), None)
        if target is None:
            raise ValidationError(self.env._("This section no longer exists."))
        zone = [inst for inst in layout if inst['zone'] == target['zone']]
        index = zone.index(target)
        other = index + (1 if step > 0 else -1)
        if 0 <= other < len(zone):
            i, j = layout.index(zone[index]), layout.index(zone[other])
            layout[i], layout[j] = layout[j], layout[i]
            self._sc_layout_save(layout, viewer)

    @api.model
    def _sc_layout_place(self, instance_id, zone, position=None, viewer=None):
        """Put an instance in ``zone`` at ``position`` (its index among that
        zone's instances once placed; None / too large = the end) — the
        drag-and-drop drop and « Déplacer vers »."""
        if zone not in ZONES:
            raise ValidationError(self.env._("Invalid dashboard layout."))
        layout = self._sc_layout(viewer)
        target = next((inst for inst in layout if inst['id'] == instance_id), None)
        if target is None:
            raise ValidationError(self.env._("This section no longer exists."))
        rest = [inst for inst in layout if inst is not target]
        target['zone'] = zone
        by_zone = {z: [inst for inst in rest if inst['zone'] == z] for z in ZONES}
        members = by_zone[zone]
        if position is None or not 0 <= position <= len(members):
            position = len(members)
        members.insert(position, target)
        self._sc_layout_save([inst for z in ZONES for inst in by_zone[z]], viewer)

    @api.model
    def _sc_layout_update(self, instance_id, enabled=None, title=None, settings=None, viewer=None):
        """One instance's switch / title / settings (strict validation)."""
        layout = self._sc_layout(viewer)
        target = next((inst for inst in layout if inst['id'] == instance_id), None)
        if target is None:
            raise ValidationError(self.env._("This section no longer exists."))
        if enabled is not None:
            target['enabled'] = bool(enabled)
        if title is not None:
            target['title'] = title
        if settings is not None:
            target['settings'] = dict(target['settings'], **settings)
        return self._sc_layout_save(layout, viewer)

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
        viewer = viewer or self._sc_viewer()
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
        viewer = viewer or self._sc_viewer()
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
        viewer = viewer or self._sc_viewer()
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
        viewer = viewer or self._sc_viewer()
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
    def _sc_data_missing_timesheets(self, teams, days_back, explicit_scope):
        """« Feuilles de temps manquantes » (review round 1): my past events
        (started in the last ``days_back`` days) assigned to me with no
        timesheet of mine — the events page's predicate
        (sports.event._sc_missing_timesheet_domain) — never cancelled;
        filtered by team only when a scope is chosen (an assignment can be
        on a team I do not staff, as « Couvertures à venir »). Newest first."""
        Event = self.env['sports.event']
        now = fields.Datetime.now()
        domain = Event._sc_missing_timesheet_domain() + [
            ('state', '!=', 'cancelled'),
            ('date_start', '<=', now),
            ('date_start', '>=', now - timedelta(days=days_back)),
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
