# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': 'Bemade Portal Kit',
    'version': '19.0.1.1.0',
    'category': 'Website/Portal',
    'summary': 'Reusable portal app shell toolkit: roles, navigation, visibility and page registries.',
    'description': """
Bemade Portal Kit
=================

A toolkit for building a role-aware app on the Odoo portal. It holds the
generic machinery of a portal « app shell »; the addons built on it (its
consumers) bring the content: their roles, menu entries, visibility keys and
pages. The kit installs on Odoo Community and depends on ``portal`` only.

Version 1.0 provides the four registries of the shell; version 1.1 adds the
shell's generic scripts (below). Templates, styles and the save / fragment
engines follow in later versions.

Registries
----------
Every registry is a hook method on the abstract model ``portal.kit``. A
consumer inherits ``portal.kit`` (``_inherit``) and extends the hook with
``super()``:

* ``_pk_roles()`` -> ``{role: {'groups': (xmlid, ...), 'app': bool, ...}}``.
  A user holds a role when they belong to any of its groups. ``'app': False``
  marks a role that does not put its holder in the app (e.g. backend users).
  Extra keys are kept for the consumer's own use.
* ``_pk_nav()`` -> a list of ``pk_nav(key, label, icon, url, include,
  sequence, placement, exclude=(), requires=None, subtitle=None)`` entries.
  ``placement`` lists where the entry shows (e.g. ``tab``, ``rail``,
  ``plus``); ``requires(ctx)`` is an optional feature gate.
* ``_pk_visibility()`` -> ``{key: {'include', 'exclude', 'system', 'model',
  'field'}}``: what a role may SEE, asked from templates by key.
* ``_pk_pages()`` -> a list of ``Page(key, url=, label=, parent=, context=,
  path=, from_url=, return_url=)``: each page's parent, crumb label and URL
  pattern. The pages with a ``path`` form the allowlist of in-app return
  URLs.

An entry re-declared under an existing key replaces it in place.

Visibility rule: an entry is visible when the user's roles intersect
``include`` and do not intersect ``exclude`` (exclude wins). A key flagged
``system`` is also visible to a system administrator, unless excluded. The
registries decide what is SHOWN, never what is ALLOWED: security stays in
access rights and record rules.

Rules for consumers
-------------------
* The hooks hold code only. Each database caches the result per registry, so
  a hook must never depend on the current user, record or request.
* Per-user roles go in ``res.users._pk_extra_roles()``, which is never
  cached. ``res.users._pk_roles()`` = the group roles + the extra roles.
* Because the registries are per database, an addon's entries exist only in
  the databases where that addon is installed.

API
---
On ``env['portal.kit']``: ``pk_roles()``, ``pk_app_roles()``,
``pk_is_visible(spec, roles)``, ``pk_visible_nav(roles, placement, ctx)``,
``pk_nav_entries()``, ``pk_nav_label(key)``, ``pk_nav_labels()``,
``pk_visibility()``, ``pk_can(key, roles, is_system=False)``,
``pk_pages()``, ``pk_match_url(url)``, ``pk_resolve(key, values,
request_url=None, request_return_url=None)`` and
``pk_safe_return_url(value, fallback, prefixes=None)``. The pure helpers
(``Page``, ``pk_nav``, ``pk_static_page``, ``pk_safe_return_url``,
``pk_readable``, ``pk_arg``) are in ``odoo.addons.bemade_portal_kit.tools``.

Scripts
-------
ES modules in ``web.assets_frontend``, imported as
``@bemade_portal_kit/js/pk_<name>``. They act on the shell's markup only,
so they are inert on other portal pages:

* ``pk_fetch``: ``pkFetch(url, options)`` (GET / POST, JSON or HTML, the
  CSRF token on every POST, a timeout) and ``PkFetchError``;
* ``pk_draft_store``: the device drafts, scoped by database and user;
* ``pk_confirm``: ``pkConfirm()`` (the confirm sheet) and
  ``pkLeavePage(message)``, which leaves a page whose access ended: back to
  the in-app referrer, else the home. The shell root sets the home with
  ``data-pk-home`` (default ``/my``) and, with
  ``data-pk-home-same-params``, the query params that name a page's
  record (a referrer showing the same record is skipped);
* ``pk_app_nav`` (the back arrow: « where you came from »),
  ``pk_user_menu``, ``pk_list_header``, ``pk_focus``, ``pk_forms``,
  ``pk_switch`` (``window.pkSwitchSync``), ``pk_live_count``,
  ``pk_date_bounds``, ``pk_contact_href``, ``pk_edit_anchor``.

Until the templates move to the kit, these scripts still read the markup
names of their first consumer (``data-sc-*`` attributes, ``o_sc_*``
classes, ``sc:*`` events).
""",
    'author': 'Bemade Inc.',
    'maintainers': ['dureposd'],
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['portal'],
    'data': [],
    'assets': {
        # Task 5197 (P2): the shell's generic scripts. assets_frontend ONLY:
        # the lazy bundle includes this one, listing them there too would
        # bind them twice (tests/test_pk_assets.py).
        'web.assets_frontend': [
            'bemade_portal_kit/static/src/js/pk_fetch.js',
            'bemade_portal_kit/static/src/js/pk_draft_store.js',
            'bemade_portal_kit/static/src/js/pk_confirm.js',
            'bemade_portal_kit/static/src/js/pk_focus.js',
            'bemade_portal_kit/static/src/js/pk_date_bounds.js',
            'bemade_portal_kit/static/src/js/pk_contact_href.js',
            'bemade_portal_kit/static/src/js/pk_edit_anchor.js',
            'bemade_portal_kit/static/src/js/pk_user_menu.js',
            'bemade_portal_kit/static/src/js/pk_list_header.js',
            'bemade_portal_kit/static/src/js/pk_forms.js',
            'bemade_portal_kit/static/src/js/pk_app_nav.js',
            'bemade_portal_kit/static/src/js/pk_switch.js',
            'bemade_portal_kit/static/src/js/pk_live_count.js',
        ],
        # The hoot unit tests (tests/test_pk_hoot.py runs them headless).
        # The modules they test are only DEFINED in the test page and run
        # per test file (hoot's lazy module loader).
        'web.assets_unit_tests_setup': [
            'bemade_portal_kit/static/src/js/pk_fetch.js',
            'bemade_portal_kit/static/src/js/pk_draft_store.js',
            'bemade_portal_kit/static/src/js/pk_confirm.js',
            'bemade_portal_kit/static/src/js/pk_app_nav.js',
        ],
        'web.assets_unit_tests': [
            'bemade_portal_kit/static/tests/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
