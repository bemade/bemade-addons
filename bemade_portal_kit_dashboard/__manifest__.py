# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': 'Bemade Portal Kit: Configurable Dashboard',
    'version': '19.0.1.1.1',
    'category': 'Website/Portal',
    'summary': 'A dashboard of widget sections each user shows, orders, places and narrows, on the portal app.',
    'description': """
Bemade Portal Kit: Configurable Dashboard
=========================================

The portal app's home (``/my/home`` while the kit's switch is on) as a
dashboard of widget sections. Each user switches sections on and off,
orders them, places them in three zones, adds more instances of a widget
with their own title and settings, and narrows a section to some records
(its scope). Community only; depends on ``bemade_portal_kit``.

This addon brings the engine, the pages and the sheet; a consumer brings
the widgets.

Engine: ``portal.kit.dashboard``
--------------------------------
An abstract model, as the viewer (record rules apply). Hooks (extend them
in an ``_inherit = 'portal.kit.dashboard'``):

* ``_pk_widgets()``: the widget registry, ``pk_dash_widget(key, title,
  zone, template, builder, can, scoped, filters, defaults, app)``. The key
  is stored in the users' layouts: never rename it. Version 1.1: ``app``
  names the consumer's app (none: every app); a viewer gets their app's
  widgets and the shared ones (``pk_dash_app_widgets(app)``), and likewise
  the filters (``pk_dash_filter(..., app=)``) and scope fields (``'app'``);
  ``viewer['app']`` is the app the dashboard is drawn in;
* ``_pk_dash_filters()``: the widgets' own settings, ``pk_dash_filter(type,
  label, choices, default)`` with type ``multi`` (switches), ``choice`` or
  ``int`` (a select); ``_pk_dash_filter_choices(name, viewer)`` narrows what
  the sheet offers;
* ``_pk_dash_viewer()`` (the viewer's roles, computed once per request) and
  ``_pk_dash_widget_title(spec, viewer)``;
* the scope: ``_pk_dash_scope_fields()`` (each a list of ids in the
  settings), ``_pk_dash_scope_universe(viewer)``,
  ``_pk_dash_scope_allowed(universe)``, ``_pk_dash_scope_options(universe)``,
  ``_pk_dash_scope_resolve(settings, viewer, universe)``,
  ``_pk_dash_scope_label(settings, scope)``, ``_pk_dash_scope_empty(scope)``
  and the wording hooks ``_pk_dash_scope_hint``,
  ``_pk_dash_scope_refused``, ``_pk_dash_scope_empty_label``,
  ``_pk_dash_intro``. A consumer's override answers for its own app
  (``viewer['app']`` / ``_pk_dash_app()``) and calls ``super()`` for any
  other.

Layout
------
``res.users.pk_dashboard_layout`` (JSON, system group only, written by the
sheet through the strict validation): ``{"v": 2, "instances": [{"id",
"widget", "zone", "enabled", "title", "settings"}]}``. Zones ``left``,
``right`` (two columns on a laptop) and ``bottom`` (full width); a phone
reads left, right, bottom. A ``v: 1`` layout (no zones) loads with its
first half left, the rest right; a stored value is never rewritten on load.
Every widget keeps its base instance (id = its key); added ones are
``<key>-<n>``. Limits: 30 instances, titles of 80 characters.

Pages
-----
* ``/my/home``: the dashboard of the viewer's app (``pk_dash_page``). An
  app that draws its own home page calls ``pk_dash_home`` from it and
  names it in its registration (``portal.kit._pk_apps()``: ``'home':
  'module.template'``, or ``'home_render': '<controller method>'`` to
  render it with its own values; version 1.1, no ``home()`` or
  ``_pk_dash_render`` override; such an app does not see ``pk_dash_page``);
  ``pk_dash_home``'s body slot (the caller's body) and
  ``_pk_dash_page_values(values, ctx)`` are the page parts extension point;
  ``_pk_dash_context(Dash, viewer)`` is what each widget builder
  (``builder(instance, scope, ctx)``) receives;
* ``/my/app/dashboard/configure`` (``pk_dash_configure``): one row per
  instance, saved as you go (``pk_dashboard_config.js``), drag and drop
  between zones on a laptop, ▲ / ▼ and « Move to » on a phone, « Add a
  section », « Remove » and « Restore the default » (both confirmed). POST
  routes ``/save``, ``/move``, ``/add``, ``/remove``, ``/reset``: JSON for
  the page's fetch, a redirect back otherwise.

``pk_dashboard_anchor.js`` keeps a fold-out's header in place on the
dashboard. Markers ``data-pk-dashboard``, ``data-pk-dash-*``; fragment keys
``pk.dashboard:<widget>:<instance>``.

Moved from the first consumer
-----------------------------
The section frame and the configure sheet keep their view records, the
users' layouts their column (renamed in place, values byte for byte): the
install hook and the consumer's pre-migration (``tools/adopt.py``).
""",
    'author': 'Bemade Inc.',
    'maintainers': ['dureposd'],
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['bemade_portal_kit'],
    'data': [
        'views/pk_dashboard_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'bemade_portal_kit_dashboard/static/src/scss/pk_dashboard.scss',
            'bemade_portal_kit_dashboard/static/src/js/pk_dashboard_config.js',
            'bemade_portal_kit_dashboard/static/src/js/pk_dashboard_anchor.js',
        ],
        'web.assets_unit_tests_setup': [
            'bemade_portal_kit_dashboard/static/src/js/pk_dashboard_config.js',
            'bemade_portal_kit_dashboard/static/src/js/pk_dashboard_anchor.js',
        ],
        'web.assets_unit_tests': [
            'bemade_portal_kit_dashboard/static/tests/*.test.js',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
}
