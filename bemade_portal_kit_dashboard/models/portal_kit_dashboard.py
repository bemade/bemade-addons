# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The configurable dashboard's engine (``portal.kit.dashboard``).

Read this before adding a dashboard widget to a consumer.

Widget registry
---------------
``_pk_widgets()`` (a consumer extends it) returns THE list of widgets, each
built with ``pk_dash_widget(...)``:

* ``key``       stable identifier, stored in the users' layouts: never rename;
* ``title``     the default section title (translatable);
* ``zone``      the zone of its base instance in the default layout;
* ``template``  the QWeb template of its body;
* ``builder``   the name of the dashboard controller's method building its
                render values, ``builder(instance, scope, ctx) -> dict``;
* ``can``       its visibility key (``portal.kit.pk_can``), or None (every
                viewer);
* ``scoped``    it takes the scope (see « Scope » below);
* ``filters``   its own settings, names of ``_pk_dash_filters()``;
* ``defaults``  a default value per filter (else the filter's default).

Other keys are kept as they are (a consumer's own wording rules, read by its
``_pk_dash_widget_title``).

Filters
-------
``_pk_dash_filters()``: ``{name: {'type', 'label', 'choices', 'default'}}``.
``type`` is ``multi`` (a subset of the choices), ``choice`` (one of them) or
``int`` (one of them, posted and stored as an integer); ``choices`` is a
sequence of ``(value, label)``. The configure sheet draws a switch per
choice (``multi``) or a select; a save accepts nothing outside the choices.
``_pk_dash_filter_choices(name, viewer)`` narrows what the sheet offers.

Per-user layout
---------------
``res.users.pk_dashboard_layout`` (JSON, written by the configure sheet
only, through ``_pk_dash_layout_save``)::

    {"v": 2, "instances": [
        {"id": "w", "widget": "w", "zone": "bottom", "enabled": true, "title": "",
         "settings": {...}},
        {"id": "w-2", "widget": "w", "zone": "right", "enabled": true,
         "title": "My own title", "settings": {...}},
        ...]}

* every instance sits in one of three ``ZONES``: ``left`` / ``right`` (two
  independent columns side by side on a laptop) and ``bottom`` (full width
  under both). On a phone the page reads left, then right, then bottom. The
  instance list is kept in that order (zone, then position in the zone);
* ``v: 1`` layouts (no zones) still load: their instances keep their order,
  the first half (rounded up) goes left, the rest right. The next save
  writes ``v: 2``. A stored value is never rewritten on load;
* several instances of one widget are allowed, each with its own settings
  and an optional custom title. Every widget keeps its BASE instance (id =
  the widget key): it can be switched off, never removed; the added ones
  (id ``<key>-<n>``) can be removed;
* a missing / invalid layout (or an unknown ``v``) falls back to the
  default; unknown widget keys and widgets the viewer may not have are
  ignored (forward compatible); a widget added to the registry later joins
  every saved layout at the end of its zone;
* a save is validated (strict): known widget, allowed for the viewer,
  setting values from their choices, scope ids the viewer may use. Anything
  else is REFUSED with a clear message, never silently fixed.

Scope
-----
A consumer may let a scoped widget be narrowed to some records: its scope
fields (``_pk_dash_scope_fields()``, each a list of record ids in the
settings, e.g. ``scope_tag_ids``), the ids the viewer may name
(``_pk_dash_scope_universe`` / ``_pk_dash_scope_allowed``), the configure
sheet's options (``_pk_dash_scope_options``), the resolution of an
instance's scope (``_pk_dash_scope_resolve``: what the widget's builder
receives), its sub-title (``_pk_dash_scope_label``) and its emptiness
(``_pk_dash_scope_empty``). Without scope fields a scoped widget has no
scope setting at all.
"""
import re

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

LAYOUT_VERSION = 2
# The versions a stored layout may have (older ones are upgraded on load).
LAYOUT_VERSIONS = (1, 2)
MAX_INSTANCES = 30
TITLE_MAX = 80
ID_RE = re.compile(r'^[a-z0-9_-]{1,40}$')

# The three zones of the page, in their phone reading order.
ZONES = ('left', 'right', 'bottom')
ZONE_TERMS = (_lt('Left'), _lt('Right'), _lt('Bottom'))
FILTER_TYPES = ('multi', 'choice', 'int')


def pk_dash_widget(key, title, zone, template, builder=None, can=None, scoped=False, filters=(),
                   defaults=None, **extra):
    """One entry of ``portal.kit.dashboard._pk_widgets()`` (a new dict)."""
    spec = dict(extra)
    spec.update({
        'key': key,
        'title': title,
        'zone': zone,
        'template': template,
        'builder': builder,
        'can': can,
        'scoped': bool(scoped),
        'filters': tuple(filters),
        'defaults': dict(defaults or {}),
    })
    return spec


def pk_dash_filter(kind, label, choices, default=None):
    """One entry of ``portal.kit.dashboard._pk_dash_filters()``."""
    return {'type': kind, 'label': label, 'choices': tuple(choices), 'default': default}


def _copy(value):
    return list(value) if isinstance(value, (list, tuple)) else value


class PortalKitDashboard(models.AbstractModel):
    """The dashboard's logic, as the viewer (``self.env.user``): the
    registry, the layout and the scope. Consumers extend the hooks
    (``_pk_widgets``, ``_pk_dash_filters``, ``_pk_dash_viewer``, the scope
    hooks) with ``_inherit = 'portal.kit.dashboard'``."""

    _name = 'portal.kit.dashboard'
    _description = 'Portal kit: configurable dashboard'

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    @api.model
    def _pk_widgets(self):
        """The widget registry: ``[pk_dash_widget(...)]`` in default layout
        order (none here). A new list on every call."""
        return []

    @api.model
    def _pk_dash_filters(self):
        """``{name: pk_dash_filter(...)}``: the widgets' own settings."""
        return {}

    @api.model
    def _pk_dash_filter_choices(self, name, viewer):
        """The ``(value, label)`` choices the configure sheet offers for
        filter ``name`` (default: all of them)."""
        return list(self._pk_dash_filters()[name]['choices'])

    @api.model
    def _pk_dash_viewer(self):
        """The viewer, computed once per request: ``roles`` (the app roles)
        and ``is_system``. A consumer adds its own keys."""
        user = self.env.user
        return {
            'roles': user._pk_roles(),
            'is_system': user.has_group('base.group_system'),
        }

    @api.model
    def _pk_dash_widget_title(self, spec, viewer=None):
        """A widget's default title for this viewer."""
        return str(spec['title'])

    # -- scope -----------------------------------------------------------
    @api.model
    def _pk_dash_scope_fields(self):
        """The scope fields, in configure order: ``[{'name', 'label',
        'placeholder'}]``; each is a list of ids in the settings (none
        here)."""
        return []

    @api.model
    def _pk_dash_scope_universe(self, viewer):
        """What a scope may name for this viewer (opaque: the consumer's
        records), computed once per layout load."""
        return None

    @api.model
    def _pk_dash_scope_allowed(self, universe):
        """``{field: set of ids}`` a scope may name (a field missing: any
        id)."""
        return {}

    @api.model
    def _pk_dash_scope_options(self, universe):
        """``{field: [(id, label)]}``: the configure sheet's choices."""
        return {}

    @api.model
    def _pk_dash_scope_resolve(self, settings, viewer, universe):
        """An instance's scope as its builder receives it (default: None,
        no limit)."""
        return None

    @api.model
    def _pk_dash_scope_empty(self, scope):
        """Does the resolved ``scope`` hold nothing (the section then says
        so instead of drawing its body)?"""
        return scope is not None and not scope

    @api.model
    def _pk_dash_scope_label(self, settings, scope):
        """The section's sub-title for its scope (default: none)."""
        return ''

    @api.model
    def _pk_dash_scope_empty_label(self):
        """What a section whose scope holds nothing says."""
        return self.env._("Nothing in this section's scope. Change it in « Configure ».")

    @api.model
    def _pk_dash_intro(self):
        """The configure sheet's first line."""
        return self.env._("Show, hide, reorder and set up each section. Changes are saved as you go.")

    @api.model
    def _pk_dash_scope_hint(self):
        """The configure sheet's hint under « Scope »."""
        return self.env._("Nothing chosen: everything you have access to.")

    @api.model
    def _pk_dash_scope_refused(self):
        """The refusal of a scope naming ids the viewer may not use."""
        return self.env._("You cannot limit a section to records you do not have access to.")

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------
    @api.model
    def _pk_dash_can(self, key, viewer=None):
        if not key:
            return True
        viewer = viewer or self._pk_dash_viewer()
        return self.env['portal.kit'].pk_can(key, viewer['roles'], is_system=viewer.get('is_system', False))

    @api.model
    def _pk_dash_widgets(self, viewer=None):
        """The registry entries this viewer may have, in registry order."""
        viewer = viewer or self._pk_dash_viewer()
        return [spec for spec in self._pk_widgets() if self._pk_dash_can(spec['can'], viewer)]

    @api.model
    def _pk_dash_widget(self, key):
        """The registry entry ``key`` (whoever may have it), or None."""
        return next((spec for spec in self._pk_widgets() if spec['key'] == key), None)

    @api.model
    def _pk_dash_zone_labels(self):
        return dict(zip(ZONES, (str(term) for term in ZONE_TERMS)))

    @api.model
    def _pk_dash_explicit(self, settings):
        """Does an instance's settings name a scope (any scope field set)?"""
        settings = settings or {}
        return any(settings.get(field['name']) for field in self._pk_dash_scope_fields())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_dash_zone_sorted(instances):
        """The instances in page order: zone by zone, each zone in its own
        order (a stable sort)."""
        return sorted(instances, key=lambda inst: ZONES.index(inst['zone']))

    @api.model
    def _pk_dash_default_settings(self, spec, filters=None):
        filters = self._pk_dash_filters() if filters is None else filters
        settings = {}
        if spec['scoped']:
            for field in self._pk_dash_scope_fields():
                settings[field['name']] = []
        for name in spec['filters']:
            default = spec['defaults'][name] if name in spec['defaults'] else filters[name]['default']
            settings[name] = _copy(default)
        return settings

    @api.model
    def _pk_dash_default_instance(self, spec, instance_id=None, zone=None, filters=None):
        return {
            'id': instance_id or spec['key'],
            'widget': spec['key'],
            'zone': zone or spec['zone'],
            'enabled': True,
            'title': '',
            'settings': self._pk_dash_default_settings(spec, filters),
        }

    @api.model
    def _pk_dash_layout_default(self, viewer=None):
        filters = self._pk_dash_filters()
        return [self._pk_dash_default_instance(spec, filters=filters) for spec in self._pk_dash_widgets(viewer)]

    @api.model
    def _pk_dash_clean_settings(self, spec, raw, strict, allowed_ids=None, filters=None):
        """``raw`` settings -> the instance's clean settings. ``strict`` (a
        save) raises on any value outside its choices / the viewer's scope;
        otherwise (a load) such values are dropped."""
        filters = self._pk_dash_filters() if filters is None else filters
        allowed_ids = allowed_ids or {}
        raw = raw if isinstance(raw, dict) else {}
        clean = self._pk_dash_default_settings(spec, filters)
        if spec['scoped']:
            for field in self._pk_dash_scope_fields():
                name = field['name']
                allowed = allowed_ids.get(name)
                ids = []
                for value in raw.get(name) or []:
                    try:
                        ids.append(int(value))
                    except (TypeError, ValueError):
                        if strict:
                            raise ValidationError(self.env._("Invalid scope.")) from None
                foreign = [i for i in ids if allowed is not None and i not in allowed]
                if foreign and strict:
                    raise ValidationError(self._pk_dash_scope_refused())
                clean[name] = sorted({i for i in ids if i not in foreign})
        for name in spec['filters']:
            if name not in raw:
                continue
            kind = filters[name]
            choices = [choice[0] for choice in kind['choices']]
            value = raw[name]
            if kind['type'] == 'multi':
                values = value if isinstance(value, (list, tuple)) else [value]
                bad = [v for v in values if v not in choices]
                if bad and strict:
                    raise ValidationError(self.env._("Invalid setting."))
                clean[name] = [c for c in choices if c in values]
            else:
                if kind['type'] == 'int':
                    try:
                        value = int(value or 0)
                    except (TypeError, ValueError):
                        value = None
                if value not in choices:
                    if strict:
                        raise ValidationError(self.env._("Invalid setting."))
                    continue
                clean[name] = value
        return clean

    @api.model
    def _pk_dash_normalize(self, raw, strict=False, viewer=None):
        """A stored / posted layout -> the clean ordered instance list for
        this viewer (see the module docstring for the rules)."""
        viewer = viewer or self._pk_dash_viewer()
        allowed = {spec['key']: spec for spec in self._pk_dash_widgets(viewer)}
        if not (isinstance(raw, dict) and raw.get('v') in LAYOUT_VERSIONS
                and isinstance(raw.get('instances'), list)):
            if strict:
                raise ValidationError(self.env._("Invalid dashboard layout."))
            return self._pk_dash_layout_default(viewer)
        if raw['v'] != LAYOUT_VERSION:
            if strict:
                raise ValidationError(self.env._("Invalid dashboard layout."))
            raw = self._pk_dash_layout_migrate(raw)
        filters = self._pk_dash_filters()
        allowed_ids = self._pk_dash_scope_allowed(self._pk_dash_scope_universe(viewer))
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
                continue  # unknown (a later version) or not for this viewer
            instance_id = str(item.get('id') or '')
            if not ID_RE.match(instance_id) or instance_id in seen or not instance_id.startswith(key):
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
                'settings': self._pk_dash_clean_settings(spec, item.get('settings'), strict, allowed_ids, filters),
            })
        if len(clean) > MAX_INSTANCES and strict:
            raise ValidationError(self.env._("Too many sections."))
        # Every widget keeps its base instance (a widget added to the
        # registry later joins the saved layouts at the end of its zone).
        for key, spec in allowed.items():
            if key not in seen:
                clean.append(self._pk_dash_default_instance(spec, filters=filters))
        return self._pk_dash_zone_sorted(clean)

    @api.model
    def _pk_dash_layout_migrate(self, raw):
        """A ``v: 1`` layout (no zones) -> ``v: 2``, in memory: the order
        kept, the first half (rounded up) in the left column, the rest in
        the right one."""
        items = [dict(item) for item in raw.get('instances') or [] if isinstance(item, dict)]
        half = (len(items) + 1) // 2
        for index, item in enumerate(items):
            item['zone'] = 'left' if index < half else 'right'
        return {'v': LAYOUT_VERSION, 'instances': items}

    @api.model
    def _pk_dash_layout(self, viewer=None):
        return self._pk_dash_normalize(self.env.user.sudo().pk_dashboard_layout, viewer=viewer)

    @api.model
    def _pk_dash_layout_save(self, instances, viewer=None):
        """Validate (strict) and store the viewer's layout; returns the
        clean instance list. sudo: the field is not self-writable on
        purpose, only this validated path writes it."""
        clean = self._pk_dash_normalize({'v': LAYOUT_VERSION, 'instances': instances}, strict=True, viewer=viewer)
        self.env.user.sudo().pk_dashboard_layout = {'v': LAYOUT_VERSION, 'instances': clean}
        return clean

    @api.model
    def _pk_dash_layout_reset(self):
        self.env.user.sudo().pk_dashboard_layout = False
        return self._pk_dash_layout()

    @api.model
    def _pk_dash_layout_add_zone(self, layout):
        """« Add a section »'s default zone: the shorter of the two columns
        (fewer shown sections; left on a tie)."""
        count = {zone: sum(1 for inst in layout if inst['zone'] == zone and inst['enabled'])
                 for zone in ('left', 'right')}
        return 'right' if count['right'] < count['left'] else 'left'

    @api.model
    def _pk_dash_find(self, layout, instance_id):
        target = next((inst for inst in layout if inst['id'] == instance_id), None)
        if target is None:
            raise ValidationError(self.env._("This section no longer exists."))
        return target

    @api.model
    def _pk_dash_layout_add(self, widget_key, viewer=None, zone=None):
        """A new instance of ``widget_key`` at the end of ``zone`` (default:
        the shorter column); returns its id."""
        viewer = viewer or self._pk_dash_viewer()
        spec = {s['key']: s for s in self._pk_dash_widgets(viewer)}.get(widget_key)
        if spec is None:
            raise ValidationError(self.env._("This section is not available to you."))
        if zone is not None and zone not in ZONES:
            raise ValidationError(self.env._("Invalid dashboard layout."))
        layout = self._pk_dash_layout(viewer)
        zone = zone or self._pk_dash_layout_add_zone(layout)
        ids = {inst['id'] for inst in layout}
        new_id = next((candidate for candidate in ('%s-%s' % (widget_key, n) for n in range(2, MAX_INSTANCES + 2))
                       if candidate not in ids), None)
        if new_id is None or len(layout) >= MAX_INSTANCES:
            raise ValidationError(self.env._("Too many sections."))
        layout.append(self._pk_dash_default_instance(spec, new_id, zone=zone))
        self._pk_dash_layout_save(self._pk_dash_zone_sorted(layout), viewer)
        return new_id

    @api.model
    def _pk_dash_layout_remove(self, instance_id, viewer=None):
        layout = self._pk_dash_layout(viewer)
        target = self._pk_dash_find(layout, instance_id)
        if target['id'] == target['widget']:
            raise ValidationError(self.env._("This section can be switched off, not removed."))
        self._pk_dash_layout_save([inst for inst in layout if inst['id'] != instance_id], viewer)

    @api.model
    def _pk_dash_layout_move(self, instance_id, step, viewer=None):
        """▲ / ▼: one step up / down WITHIN its zone (no-op at its edge)."""
        layout = self._pk_dash_layout(viewer)
        target = self._pk_dash_find(layout, instance_id)
        zone = [inst for inst in layout if inst['zone'] == target['zone']]
        index = zone.index(target)
        other = index + (1 if step > 0 else -1)
        if 0 <= other < len(zone):
            i, j = layout.index(zone[index]), layout.index(zone[other])
            layout[i], layout[j] = layout[j], layout[i]
            self._pk_dash_layout_save(layout, viewer)

    @api.model
    def _pk_dash_layout_place(self, instance_id, zone, position=None, viewer=None):
        """Put an instance in ``zone`` at ``position`` (its index among that
        zone's instances once placed; None / too large = the end): the
        drag-and-drop drop and « Move to »."""
        if zone not in ZONES:
            raise ValidationError(self.env._("Invalid dashboard layout."))
        layout = self._pk_dash_layout(viewer)
        target = self._pk_dash_find(layout, instance_id)
        rest = [inst for inst in layout if inst is not target]
        target['zone'] = zone
        by_zone = {z: [inst for inst in rest if inst['zone'] == z] for z in ZONES}
        members = by_zone[zone]
        if position is None or not 0 <= position <= len(members):
            position = len(members)
        members.insert(position, target)
        self._pk_dash_layout_save([inst for z in ZONES for inst in by_zone[z]], viewer)

    @api.model
    def _pk_dash_layout_update(self, instance_id, enabled=None, title=None, settings=None, viewer=None):
        """One instance's switch / title / settings (strict validation)."""
        layout = self._pk_dash_layout(viewer)
        target = self._pk_dash_find(layout, instance_id)
        if enabled is not None:
            target['enabled'] = bool(enabled)
        if title is not None:
            target['title'] = title
        if settings is not None:
            target['settings'] = dict(target['settings'], **settings)
        return self._pk_dash_layout_save(layout, viewer)
