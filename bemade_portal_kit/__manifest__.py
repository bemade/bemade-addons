# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': 'Bemade Portal Kit',
    'version': '19.0.1.0.0',
    'category': 'Website/Portal',
    'summary': 'Reusable portal app shell toolkit: roles, navigation, visibility and page registries.',
    'description': """
Bemade Portal Kit
=================

A toolkit for building a role-aware app on the Odoo portal. It holds the
generic machinery of a portal « app shell »; the addons built on it (its
consumers) bring the content: their roles, menu entries, visibility keys and
pages. The kit installs on Odoo Community and depends on ``portal`` only.

This first version provides the four registries of the shell. Templates,
styles, scripts and the save / fragment engines follow in later versions.

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
""",
    'author': 'Bemade Inc.',
    'maintainers': ['dureposd'],
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['portal'],
    'data': [],
    'installable': True,
    'application': False,
}
