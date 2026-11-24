# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The configurable dashboard's pages (task 5202, kit P7; moved from the
first consumer, same URLs and answers).

* ``/my/home`` while the app's switch is on: the dashboard of the viewer's
  app (task 5391: ``portal.kit._pk_apps()[app]``: ``home``, a page that
  calls ``pk_dash_home``, or ``home_render``, the name of a controller
  method ``(values) -> response`` drawing it; default: ``pk_dash_page`` on
  the app layout). A consumer never overrides ``home()`` /
  ``_pk_dash_render`` for that;
* ``/my/app/dashboard/configure``: the configure sheet (``pk_dash_configure``)
  and its POST routes ``/save``, ``/move``, ``/add``, ``/remove``,
  ``/reset``. Each answers JSON ``{ok}`` / ``{ok: false, error}`` (400) to
  the page's fetch (``X-Requested-With: XMLHttpRequest``), else redirects
  back to the sheet (PRG, the refusal shown there). Every POST is validated
  by ``portal.kit.dashboard`` (strict).

Extension points (a consumer's controller that inherits ``PortalKitShell``
is merged with this one, its overrides win):

* ``_pk_dash_context(Dash, viewer)``: the context every widget builder
  receives (``viewer``, ``universe``, plus the consumer's own; a consumer
  adds its keys for its own app only, ``viewer['app']``);
* the builders, ``builder(instance, scope, ctx) -> dict`` (named by each
  widget's ``builder``);
* ``_pk_dash_page_values(values, ctx)``: the page parts, the values the
  page needs besides its sections (a consumer's sheets, kept rows…); the
  template's body slot (``pk_dash_home``'s caller body) draws them.
"""
from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.bemade_portal_kit.controllers.pk_shell import PortalKitShell
from odoo.addons.bemade_portal_kit.tools import pk_form_props

from ..models.portal_kit import PK_DASH_CONFIGURE_URL
from ..models.portal_kit_dashboard import ZONES

# Rows shown in a section before « See the N others » (a builder that
# returns ``rows`` gets ``rows_shown`` / ``more_rows_label``).
PK_DASH_ROWS_SHOWN = 8


def pk_csv_ints(value):
    """``"1, 2"`` -> ``[1, 2]``; anything else refused (« Invalid scope. »)."""
    ids = []
    for part in str(value or '').split(','):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except ValueError:
                raise ValidationError(request.env._("Invalid scope.")) from None
    return ids


class PortalKitDashboard(PortalKitShell):

    # ------------------------------------------------------------------
    # The dashboard
    # ------------------------------------------------------------------
    @http.route()
    def home(self, **kw):
        if kw.get('classic') or not self._pk_shell_active():
            return super().home(**kw)
        values = self._prepare_portal_layout_values()
        values.update(self._pk_dash_values())
        return self._pk_dash_render(values)

    def _pk_dash_render(self, values):
        """The home's response: the viewer's app's ``home_render`` method
        (task 5391), else ``_pk_dash_home_template()`` drawn by
        ``_pk_page``."""
        method = request.env['portal.kit'].pk_app_spec().get('home_render')
        if method:
            return getattr(self, method)(values)
        return self._pk_page(self._pk_dash_home_template(), values)

    def _pk_dash_home_template(self):
        """The home's template: the viewer's app's ``home`` (a page that
        calls ``pk_dash_home``, its page key the template's name), else
        ``pk_dash_page``."""
        return (request.env['portal.kit'].pk_app_spec().get('home')
                or 'bemade_portal_kit_dashboard.pk_dash_page')

    def _pk_dash_context(self, Dash, viewer):
        """What every builder receives as ``ctx`` (a consumer adds its own
        keys; page parts a widget asks for go here too)."""
        return {'viewer': viewer, 'universe': Dash._pk_dash_scope_universe(viewer)}

    def _pk_dash_build(self, spec, instance, scope, ctx):
        builder = spec.get('builder')
        return getattr(self, builder)(instance, scope, ctx) if builder else {}

    def _pk_dash_values(self):
        """The dashboard's values: its sections, by zone, and the page
        parts (``_pk_dash_page_values``)."""
        env = request.env
        Dash = env['portal.kit.dashboard']
        viewer = Dash._pk_dash_viewer()
        ctx = self._pk_dash_context(Dash, viewer)
        sections = []
        for instance in Dash._pk_dash_layout(viewer):
            if not instance['enabled']:
                continue
            spec = Dash._pk_dash_widget(instance['widget'], app=viewer.get('app'))
            scope = None
            if spec['scoped']:
                scope = Dash._pk_dash_scope_resolve(instance['settings'], viewer, ctx['universe'])
            values = self._pk_dash_build(spec, instance, scope, ctx)
            section = {
                'id': instance['id'],
                'widget': spec['key'],
                'zone': instance['zone'],
                'template': spec['template'],
                'title': instance['title'] or Dash._pk_dash_widget_title(spec, viewer),
                'scope_label': Dash._pk_dash_scope_label(instance['settings'], scope) if spec['scoped'] else '',
                'no_scope': bool(spec['scoped'] and Dash._pk_dash_scope_empty(scope)),
                'no_scope_label': Dash._pk_dash_scope_empty_label() if spec['scoped'] else '',
                'row_scope': 'dash-%s' % instance['id'],
            }
            section.update(values)
            rows = section.get('rows') or []
            section['rows_shown'] = PK_DASH_ROWS_SHOWN
            section['more_rows_label'] = (
                env._("See the %(count)s others", count=len(rows) - PK_DASH_ROWS_SHOWN)
                if len(rows) > PK_DASH_ROWS_SHOWN else '')
            sections.append(section)
        values = {
            'pk_dash_sections': sections,
            'pk_dash_zones': self._pk_dash_zones(sections),
            'pk_dash_configure_url': PK_DASH_CONFIGURE_URL,
        }
        return self._pk_dash_page_values(values, ctx)

    def _pk_dash_page_values(self, values, ctx):
        """The page parts: ``values`` + what the page needs besides its
        sections (default: nothing)."""
        return values

    @staticmethod
    def _pk_dash_zones(sections):
        """The sections by zone, in page order; a side column alone (the
        other one empty) is ``solo``: full width on a laptop."""
        zones = [{'zone': zone, 'sections': [sec for sec in sections if sec['zone'] == zone]}
                 for zone in ZONES]
        left, right = zones[0], zones[1]
        left['solo'] = not right['sections']
        right['solo'] = not left['sections']
        return zones

    # ------------------------------------------------------------------
    # The configure sheet
    # ------------------------------------------------------------------
    def _pk_dash_configure_row(self, Dash, instance, layout, viewer, filters, scope_fields, scope_options):
        env = request.env
        spec = Dash._pk_dash_widget(instance['widget'], app=viewer.get('app'))
        settings = instance['settings']
        zone_ids = [inst['id'] for inst in layout if inst['zone'] == instance['zone']]
        row = {
            'id': instance['id'],
            'widget': spec['key'],
            'zone': instance['zone'],
            'widget_title': Dash._pk_dash_widget_title(spec, viewer),
            'title': instance['title'],
            'enabled': instance['enabled'],
            'removable': instance['id'] != spec['key'],
            # ▲ / ▼ move within the zone.
            'first': zone_ids[0] == instance['id'],
            'last': zone_ids[-1] == instance['id'],
            'scoped': bool(spec['scoped'] and scope_fields),
            'settings': settings,
            'scope': [],
            'filters': [],
        }
        if row['scoped']:
            for field in scope_fields:
                target = 'pk_dash_%s_%s' % (instance['id'], field['name'])
                csv = ','.join(str(i) for i in settings.get(field['name']) or [])
                row['scope'].append({
                    'name': field['name'],
                    'target': target,
                    'csv': csv,
                    'props': pk_form_props(target, str(field['label']), 'tags', csv,
                                           options=scope_options.get(field['name']) or [],
                                           placeholder=str(field.get('placeholder') or '')),
                })
        for name in spec['filters']:
            decl = filters[name]
            value = settings.get(name)
            choices = Dash._pk_dash_filter_choices(name, viewer)
            if decl['type'] == 'multi':
                options = [(choice, str(label), choice in (value or ())) for choice, label in choices]
            else:
                options = [(choice, str(label), value == choice) for choice, label in choices]
            row['filters'].append({
                'name': name,
                'type': decl['type'],
                'label': str(decl['label']),
                'id': 'pk_dash_%s_%s' % (instance['id'], name),
                'choices': options,
            })
        return row

    @http.route([PK_DASH_CONFIGURE_URL], type='http', auth='user', website=True)
    def pk_dash_configure(self, **kw):
        if not self._pk_shell_active():
            return request.redirect('/my/home')
        Dash = request.env['portal.kit.dashboard']
        viewer = Dash._pk_dash_viewer()
        layout = Dash._pk_dash_layout(viewer)
        filters = Dash._pk_dash_app_filters(viewer.get('app'))
        scope_fields = Dash._pk_dash_app_scope_fields(viewer.get('app'))
        scope_options = Dash._pk_dash_scope_options(Dash._pk_dash_scope_universe(viewer)) if scope_fields else {}
        rows = [self._pk_dash_configure_row(Dash, instance, layout, viewer, filters, scope_fields, scope_options)
                for instance in layout]
        labels = Dash._pk_dash_zone_labels()
        zone_choices = [(zone, labels[zone]) for zone in ZONES]
        values = self._prepare_portal_layout_values()
        values.update({
            'pk_dash_rows': rows,
            # The rows by zone, as on the dashboard.
            'pk_dash_cfg_zones': [
                {'zone': zone, 'label': label, 'rows': [row for row in rows if row['zone'] == zone]}
                for zone, label in zone_choices],
            'pk_dash_zone_choices': zone_choices,
            'pk_dash_add_zone': Dash._pk_dash_layout_add_zone(layout),
            'pk_dash_add_choices': [(spec['key'], Dash._pk_dash_widget_title(spec, viewer))
                                    for spec in Dash._pk_dash_widgets(viewer)],
            'pk_dash_intro': Dash._pk_dash_intro(),
            'pk_dash_scope_hint': Dash._pk_dash_scope_hint() if scope_fields else '',
            'pk_dash_url': PK_DASH_CONFIGURE_URL,
            'pk_dash_home_url': '/my/home',
            'pk_dash_error': request.session.pop('pk_dash_error', None),
        })
        return self._pk_page('bemade_portal_kit_dashboard.pk_dash_configure', values)

    @staticmethod
    def _pk_dash_wants_json():
        return request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _pk_dash_done(self, anchor=None, error=None):
        """Answer a configure POST: JSON for the page's fetch, else back to
        the page (PRG), the refusal shown there."""
        if self._pk_dash_wants_json():
            if error:
                return request.make_json_response({'ok': False, 'error': error}, status=400)
            return request.make_json_response({'ok': True})
        if error:
            request.session['pk_dash_error'] = error
        return request.redirect(PK_DASH_CONFIGURE_URL + ('#pk-dash-%s' % anchor if anchor else ''))

    def _pk_dash_post(self, run, anchor=None):
        if not self._pk_shell_active():
            return request.redirect('/my/home')
        try:
            result = run(request.env['portal.kit.dashboard'])
        except ValidationError as error:
            return self._pk_dash_done(anchor, error=str(error.args[0] if error.args else error))
        return self._pk_dash_done(result or anchor)

    @staticmethod
    def _pk_dash_parse_settings(Dash, post):
        """The posted settings: the scope fields (comma-separated ids), the
        filters (a ``multi`` one with its ``<name>_present`` marker, so that
        none ticked is « none »)."""
        settings = {}
        for field in Dash._pk_dash_app_scope_fields():
            if field['name'] in post:
                settings[field['name']] = pk_csv_ints(post.get(field['name']))
        for name, decl in Dash._pk_dash_app_filters().items():
            if decl['type'] == 'multi':
                if post.get('%s_present' % name):
                    settings[name] = request.httprequest.form.getlist(name)
            elif name in post:
                settings[name] = post.get(name)
        return settings

    @http.route([PK_DASH_CONFIGURE_URL + '/save'], type='http', auth='user', website=True, methods=['POST'])
    def pk_dash_configure_save(self, instance_id=None, **post):
        def run(Dash):
            settings = self._pk_dash_parse_settings(Dash, post)
            enabled = None
            if 'enabled' in post:
                enabled = post.get('enabled') not in ('0', '', 'false')
            Dash._pk_dash_layout_update(
                instance_id, enabled=enabled,
                title=post.get('title') if 'title' in post else None,
                settings=settings or None)
        return self._pk_dash_post(run, instance_id)

    @http.route([PK_DASH_CONFIGURE_URL + '/move'], type='http', auth='user', website=True, methods=['POST'])
    def pk_dash_configure_move(self, instance_id=None, step=None, zone=None, position=None, **post):
        """▲ / ▼ (``step``) within the zone; or a ``zone`` and an optional
        ``position`` in it: « Move to » and the drag-and-drop drop."""
        def run(Dash):
            if zone:
                try:
                    index = int(position) if position not in (None, '') else None
                except (TypeError, ValueError):
                    raise ValidationError(request.env._("Invalid dashboard layout.")) from None
                Dash._pk_dash_layout_place(instance_id, zone, index)
            else:
                Dash._pk_dash_layout_move(instance_id, -1 if step == 'up' else 1)
        return self._pk_dash_post(run, instance_id)

    @http.route([PK_DASH_CONFIGURE_URL + '/add'], type='http', auth='user', website=True, methods=['POST'])
    def pk_dash_configure_add(self, widget=None, zone=None, **post):
        return self._pk_dash_post(lambda Dash: Dash._pk_dash_layout_add(widget, zone=zone or None))

    @http.route([PK_DASH_CONFIGURE_URL + '/remove'], type='http', auth='user', website=True, methods=['POST'])
    def pk_dash_configure_remove(self, instance_id=None, **post):
        return self._pk_dash_post(lambda Dash: Dash._pk_dash_layout_remove(instance_id))

    @http.route([PK_DASH_CONFIGURE_URL + '/reset'], type='http', auth='user', website=True, methods=['POST'])
    def pk_dash_configure_reset(self, **post):
        def run(Dash):
            Dash._pk_dash_layout_reset()
        return self._pk_dash_post(run)
