# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': 'Bemade Portal Kit',
    'version': '19.0.1.18.0',
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
shell's generic scripts (below), later versions its styles and first
templates; version 1.6 its save engine and screen refresh; version 1.7 its
form guard, status pills and lazy edit views; version 1.8 its toast, session
notification and undo; version 1.9 its edit cards, sheets, tabs, lazy load
and clamps; version 1.10 its autosave field; version 1.11 its app layout,
user menu and shell components; version 1.12 the app's switch, its
preferences, settings, « More », account and security pages, help,
search, calendar and picker; version 1.15 scopes every registry per app
(several consumers in one database, below); version 1.17 the
notification preferences; version 1.18 their phone switch.

Registries
----------
Every registry is a hook method on the abstract model ``portal.kit``. A
consumer inherits ``portal.kit`` (``_inherit``) and extends the hook with
``super()``:

* ``_pk_apps()`` -> ``{app: {...}}`` (version 1.15): each app's
  registration, see « Apps » below.
* ``_pk_roles()`` -> ``{role: {'groups': (xmlid, ...), 'app': key, ...}}``.
  A user holds a role when they belong to any of its groups. ``'app'``
  names the consumer's app (``'app': 'myapp'``; the legacy ``True``, or no
  key, is the app ``'default'``); ``'app': False``
  marks a role that does not put its holder in the app (e.g. backend users).
  Extra keys are kept for the consumer's own use.
* ``_pk_nav()`` -> a list of ``pk_nav(key, label, icon, url, include,
  sequence, placement, exclude=(), requires=None, subtitle=None, app=None)``
  entries.
  ``placement`` lists where the entry shows (e.g. ``tab``, ``rail``,
  ``plus``); ``requires(ctx)`` is an optional feature gate.
* ``_pk_visibility()`` -> ``{key: {'include', 'exclude', 'system', 'model',
  'field'}}``: what a role may SEE, asked from templates by key.
* ``_pk_pages()`` -> a list of ``Page(key, url=, label=, parent=, context=,
  path=, from_url=, return_url=, app=)``: each page's parent, crumb label
  and URL pattern. The pages with a ``path`` form the allowlist of in-app
  return URLs.

An entry re-declared under an existing key (of the same app) replaces it in
place.

Apps (version 1.15)
-------------------
Several consumers may be installed in one database (the bemade-addons CI
installs them all). Each declares an APP and every lookup is resolved in
the viewer's app, so one consumer's pages, menus, tiles and layout never
reach another's users, whatever the load order.

How to declare an app:

1. Give each of your roles your app's key: ``'app': 'myapp'`` (a role that
   does not put its holder in an app keeps ``'app': False``). Role names
   are global: prefix them if another consumer may use the same name.
2. Tag every entry you register with it: ``pk_nav(..., app='myapp')``,
   ``Page(..., app='myapp')`` / ``pk_static_page(..., app='myapp')``,
   ``pk_dash_widget(..., app='myapp')``, ``pk_dash_filter(...,
   app='myapp')``, a scope field's and a search provider's ``'app'``. An
   entry without an app is SHARED by every app (the kit's « Settings »,
   « More », « Install the app », account and security pages). To change a
   shared entry for your app, re-declare its key with your app: it replaces
   the shared one for your app only.
3. Register the app in ``_pk_apps()`` (all keys optional; extend with
   ``super()``)::

       {'myapp': {
           'sequence': 10,                  # the order of the apps
           'layout': 'myapp.my_layout',     # the kit's own pages' layout
           'brand': {...} or callable(kit), # merged over _pk_brand()
           'home': 'myapp.my_home',         # the dashboard's home page
           'home_render': 'method',         # or a controller method(values)
           'pref_fields': {field: values},  # added to /my/app/pref's
           'help_keys': {page: help key}, 'help_tabbed': (help key, ...),
           'search_placeholder': _lt('...'),
           'pwa': {'start_url', 'manifest_id', 'shortcuts' (a list or
                   callable(kit)), 'offline_style' (a dict or
                   callable(kit, pwa))},
       }}

   These replace overriding ``_pk_layout``, ``_pk_pref_fields``,
   ``_pk_search_placeholder``, ``_pk_help_keys`` / ``_pk_help_tabbed``,
   the ``_pk_pwa_*`` hooks, the dashboard's ``_pk_dash_render`` or the
   portal's ``home()`` (the kit dispatches ``/my/home`` to the app's home).

One portal app per instance (version 1.16): a production database runs ONE
app; several apps in one database exist for the bemade-addons CI, which
installs every consumer together. So:

* Register your brand in ``_pk_apps()[app]['brand']``, not page by page. It
  is the whole shell's: your pages, the kit's neutral pages (settings,
  « More », account, security, install, style guide) for every viewer,
  a user without an app role included (the default app), and the installed
  app's name, colours and start URL when the company's Portal App fields are
  empty. No app registered: the kit's neutral look. A page's ``pk_brand``
  still wins for that page.
* Home: without ``bemade_portal_kit_dashboard``, ``/my`` and ``/my/home``
  send a user in an app (switch on, an app role) to the app's home, its
  brand's ``home_url`` (``portal.kit._pk_home_url()``), in the request's
  language; ``?classic=1``, the users without an app role and a brand home
  of ``/my`` get the portal home. With the dashboard, ``/my/home`` is the
  dashboard's home of the app. A consumer no longer redirects ``/my``
  itself (it may still extend the controller's ``home()`` for users without
  an app role).
* Tests (``bemade_portal_kit/tests/common.py``): a test of the kit's own
  look sets aside whatever app the CI installed (``pk_no_apps(env)``, or
  ``pk_kit_shell``, which also does it); a test of app behaviour registers
  its own synthetic app (``pk_hooks(env, _pk_apps=..., _pk_roles=...)``).
  A test that asserts texts or URLs in one language forces it
  (``pk_frontend_langs(env, 'en_US', others)`` in ``setUpClass``, before
  creating its users): a consumer's site may default to French.

The viewer's app is ``_pk_app(user)``: the app of their app roles (several:
the lowest ``sequence``, then the lowest key). A user without an app role,
and the public pages (``/my/app.webmanifest``), read the database's default
app ``_pk_default_app()``: the system parameter
``bemade_portal_kit.default_app`` when it names an app, else the only app,
else the first one. ``_pk_current_app()`` is that resolution for the
current request. Every accessor takes ``app=None`` (default: the current
app): ``pk_pages``, ``pk_match_url``, ``pk_resolve``, ``pk_visible_nav``,
``pk_nav_entries``, ``pk_nav_label``, ``pk_nav_labels``,
``pk_search_providers``, ``pk_brand``; a URL matches the app's own pages
before the shared ones. A hook that builds a cached registry and reads
another one names its app (``pk_nav_label('teams', app='myapp')``). Save
specs and visibility keys stay global (keyed by model / key, checked
against the roles).

Visibility rule: an entry is visible when the user's roles intersect
``include`` and do not intersect ``exclude`` (exclude wins). A key flagged
``system`` is also visible to a system administrator, unless excluded. The
registries decide what is SHOWN, never what is ALLOWED: security stays in
access rights and record rules.

Rules for consumers
-------------------
* The hooks hold code only. Each database caches the result per registry, so
  a hook must never depend on the current user, record or request.
* Hooks resolve per app, never per user (version 1.15): an override that
  answers for its own app only tests the app
  (``self._pk_current_app() == 'myapp'``, the dashboard's
  ``viewer['app']``) and calls ``super()`` for every other app. Never test
  the user's groups to tell two consumers apart.
* Per-user roles go in ``res.users._pk_extra_roles()``, which is never
  cached. ``res.users._pk_roles()`` = the group roles + the extra roles.
* Because the registries are per database, an addon's entries exist only in
  the databases where that addon is installed.

API
---
On ``env['portal.kit']``: ``pk_roles()``, ``pk_app_roles(app=None)``,
``pk_apps()``, ``pk_app_spec(app=None)``, ``_pk_app(user=None)``,
``_pk_default_app()``, ``_pk_current_app()``,
``pk_is_visible(spec, roles)``, ``pk_visible_nav(roles, placement, ctx,
app=None)``, ``pk_nav_entries(app=None)``, ``pk_nav_label(key,
app=None)``, ``pk_nav_labels(app=None)``, ``pk_visibility()``,
``pk_can(key, roles, is_system=False)``, ``pk_pages(app=None)``,
``pk_match_url(url, app=None)``, ``pk_resolve(key, values,
request_url=None, request_return_url=None, app=None)`` and
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

Markup contract
---------------
The scripts read and write ``pk`` names (version 1.2; classes, tokens and
theme attribute since version 1.3):

* attributes ``data-pk-*``: ``app-shell``, ``db`` and ``uid`` on the shell
  root; ``back``; ``section``, ``edit-card``, ``edit-done``,
  ``fragment-item``; ``list-add-toggle``, ``list-add-cancel``,
  ``draft-prefix``, ``submitted``, ``submitting``; ``autosubmit``,
  ``autosubmit-fallback``, ``filter-reset``; ``user-menu-toggle``,
  ``user-menu-popup``, ``menu-toggle``, ``menu-popup``; ``confirm``,
  ``confirm-ok``, ``confirm-cancel``; ``switch-submit``, ``switch-off``;
  ``live-count-url``, ``live-eager``, ``live-hide-zero``, ``live-poll``,
  ``live-tone-on``, ``live-tone-off``; ``display-href``;
* hooks a consumer sets on its own markup: ``data-pk-focus-skip`` (a field
  that never takes the focus, e.g. a picker's search box),
  ``data-pk-keep-in-view`` (a menu popup kept inside the content area) and
  ``data-pk-list-reset`` (an always-open add card reset like an add panel);
* events ``pk:fragments``, ``pk:form-reset``, ``pk:create-success``,
  ``pk:lazy-loaded``, ``pk:live-count-refresh``, ``pk:fetch-error``,
  ``pk:nav-sync``;
* storage keys ``pk_draft:``, ``pk_pending_toast:v1``
  (``PENDING_TOAST_KEY``), ``pk_nav_*:v1`` (``NAV_STACK_KEY``,
  ``NAV_BF_RELOAD_KEY``) and ``pk_filters_open:``. A consumer imports the
  exported constants, never repeats the strings. A device draft stored
  under the old ``sc_draft:`` prefix is moved under ``pk_draft:`` when read.

* classes ``o_pk_*``, the shell's generic components: the shell root
  ``o_pk_app`` (outside of which the scripts are inert), the app bar, rail,
  tabs, crumbs, cards and edit cards, rows, lists and add panels, fields,
  pickers, pills, chips, sheets, toasts, switches and their parts. The
  scripts read ``o_pk_app``, ``o_pk_appbar``, ``o_pk_content``,
  ``o_pk_crumbs``, ``o_pk_list_add_panel``, ``o_pk_disclosure`` and
  ``o_pk_switch``; they write ``o_pk_back_useful``, ``o_pk_popup_end`` /
  ``o_pk_popup_up``, the confirm sheet's ``o_pk_sheet`` classes and a live
  chip's tone ``o_pk_chip_<tone>`` (``red``, ``orange``, ``yellow``,
  ``green``, ``secondary``, ``ghost``);
* style tokens ``--pk-*``: the colour slots (``bg``, ``surface``,
  ``surface-2``, ``line``, ``fg``, ``fg-2``, ``fg-3``, ``accent``,
  ``accent-fg``, ``secondary``, ``ok``, ``warn``, ``bad``, ``overdue``,
  ``tone-fg``, ``bar*``, ``hover``, ``focus``, ``shadow``), the fonts
  (``font-title``, ``font-text``) and the scales (``text-*``, ``title-*``,
  ``space-1`` to ``space-6``, ``radius-*``, ``tap``, ``rail-width``,
  ``appbar-height``, ``tabs-height``, ``switch-*``, ``ribbon-h``);
* the theme attribute ``data-pk-theme`` (``dark`` or ``light``) on the
  shell root.

Styles
------
Version 1.4 moves the shell's generic styles into the kit (SCSS in
``web.assets_frontend``, in this order):

* ``pk_variables.scss``: ``$pk-laptop`` (992 px, the one generic
  breakpoint) and the picker icons ``$pk-icon-calendar`` /
  ``$pk-icon-clock``;
* ``pk_tokens.scss``: every ``--pk-*`` slot with NEUTRAL defaults (slate
  greys, one blue accent, the system font stack, no web font), LIGHT on
  ``.o_pk_app`` and ``body.o_pk_app_body``, dark under
  ``[data-pk-theme="dark"]`` (body: ``o_pk_app_body_dark``). The mixins
  ``pk-scale-tokens``, ``pk-theme-light`` and ``pk-theme-dark`` are
  public;
* ``pk_components.scss`` and ``pk_pages.scss``: the components, scoped
  under ``.o_pk_app``. They read the slots only.

Slots added in 1.4: ``title-transform``, ``title-spacing``,
``appbar-title-spacing``, ``label-transform``, ``label-spacing``,
``stat-label-spacing`` (letter case and tracking: normal case in the
kit), ``brand-mark``, ``avatar-bg``, ``avatar-fg``, ``secondary-fg``,
``install-icon-bg``, ``close-filter`` and ``color-scheme``.

A consumer brands the shell by setting the slots in its own stylesheet, on
the same roots with at least the kit's specificity (``.o_pk_app``,
``.o_pk_app[data-pk-theme="dark"]``, ``.o_pk_app[data-pk-theme="light"]``
and the body's), and keeps its own rules for its own classes. The brand
palette (``--sc-*`` colours) and fonts stay with the first consumer.

Templates
---------
Version 1.5 adopts the first generic templates of the shell (QWeb, called
with ``t-call="bemade_portal_kit.<name>"``):

* ``pk_frontend_layout``: ``web.frontend_layout`` with one viewport meta
  (``viewport-fit=cover``);
* ``pk_icon``: an inline SVG icon (24 x 24, stroke ``currentColor``),
  variable ``icon`` (e.g. ``plus``, ``edit``, ``trash``, ``search``,
  ``calendar``); an unknown name renders three dots. A consumer adds its own
  glyphs by inheriting ``pk_icon_extra`` (an xpath before its ``t-else``,
  each glyph a ``t-elif``);
* ``pk_card``, ``pk_section_header``, ``pk_stat_tile``, ``pk_status_chip``,
  ``pk_empty_state``, ``pk_list_add_cancel`` and ``pk_edit_card_done``.

They were the first consumer's templates: their records keep their ids
(inheriting views and translations stay) and only their external ids
change, in a pre-migration of the kit and of the consumer, and in the
kit's ``pre_init_hook`` when the kit is installed into a database that has
the consumer already (version 1.6.1; ``tools/adopt.py``, ``ADOPTED_VIEWS``).

The glyphs are taken from, or drawn after, Feather Icons 4.29 (MIT License,
copyright Cole Bemis): ``static/src/icons/LICENSE-feather.txt``.

Save engine
-----------
Version 1.6 moves the field-by-field save of the shell into the kit:
``POST /my/app/save/<model>/<id>`` (``field``, ``value``, ``write_date``,
optional ``old_value`` and ``confirm=1``; CSRF) answers 200 (saved, with the
value, its display, the fragments to refresh, ``saved_at``…), 409 (changed
since), 403, 400 or 428 (confirm first). A consumer's portal controller
inherits ``controllers.pk_app.PortalKitApp`` and never declares the route.

What may be saved, and by whom, is the hook ``portal.kit._pk_save_specs()``
-> ``{model: spec}`` (``tools/save.py`` documents a spec: ``fields`` per role,
``check``, ``write``, ``read``, ``display``, ``hint``, ``refresh``,
``propose``, ``live_counts``, ``sudo_write`` + ``permission``, ``context``,
``confirm``, ``before_write`` / ``after_write``). The kit declares
``mail.activity`` (summary, due date, assignee, note); a consumer sets who
may act and to whom an activity may go with
``_pk_activity_can_act(activity)`` and
``_pk_activity_assignable_users(activity)``.

Screen refresh
--------------
A read-only region of a page carries ``data-pk-fragment="<key>"``
(``pk_fragment_key(record, part)``). A save answers the key patterns its
spec's ``refresh`` names; the script ``pk_fragments`` re-asks the page with
the header ``X-Pk-Fragments`` and swaps the regions in place. A page route
answers it with ``PortalKitApp._pk_render(template, values)`` (or
``_pk_fragment_keys()`` + ``_pk_fragments_response()``); fillers
(``portal.kit._pk_fragment_fillers()``) may add regions the render missed.
Markers: ``data-pk-fragment``, ``-fragment-mode="list"``,
``-fragment-keep``, ``-fragment-keep-empty``, ``data-pk-keep-open``,
``data-pk-rendered-at`` (shell root) and ``data-pk-no-dirty`` (a POST form
that changes no data). Events: ``pk:saved`` (a save's ``result``),
``pk:refresh`` and ``pk:refresh-now``; storage key ``pk_dirty_at:v1``.

Form guard
----------
Version 1.7 (``pk_form_guard``): a form marked ``data-pk-guard`` keeps its
primary action greyed, with a reason line, until it can succeed. Required
fields (``required`` / ``data-pk-required``) and the JSON rules of
``data-pk-guard-rules``, each evaluated by the rule of its ``type`` in the
JS registry ``pk_guard_rules`` (the kit registers ``required``,
``together``, ``after`` and ``not_future``; a consumer adds its own:
``{missing(rule, ctx)}`` or ``{check(rule, ctx)}``). A field may hold the
form with ``data-pk-guard-block``. ``data-pk-guard-mode``: ``native``
(default), ``fetch`` (posted with fetch and the header ``X-Pk-Guard``, a
refusal shown in the form: ``data-pk-flash-error``, ``data-pk-error-for``,
``data-pk-field-error`` or an error param) or ``manual`` (the form's own
script drives it with the exported helpers). Texts and error params:
``[data-pk-guard-texts]`` (``data-missing``, ``-generic``, ``-offline``,
``data-pk-guard-error-params``); the kit has its own texts. Slots:
``bemade_portal_kit.pk_form_guard_slots`` (``guard_id``). Server:
``PortalKitApp._pk_guard_probe()`` and ``tools.PK_GUARD_HEADER``. Classes
``o_pk_guard_reason``, ``o_pk_reason_flash``.

Status pills and lazy edit
--------------------------
``bemade_portal_kit.pk_status_pill_select`` (``pill``, ``editable``,
``compact``, ``scope``, ``undo_message``) and ``pk_status_pills``: a pick
saves through the save engine; markers ``data-pk-pill-*``, ``data-pk-model``,
``-record-id``, ``-field``, ``-write-date``, ``-old-value``,
``-undo-message``; events ``pk:pill-action`` (a pick handed to its owner)
and ``pk:toast`` (``{message, actionLabel, action}``, the page shows it).
``pk_lazy_edit`` (public interaction ``bemade_portal_kit.pk_lazy_edit``):
an edit view's fields kept in ``<template data-pk-lazy-edit>`` inside
``[data-pk-lazy-edit-host]`` are mounted on ``pk:edit-view-open``, once
(``data-pk-lazy-mounted``).

Both templates were the first consumer's (adopted like the 1.5 templates,
``ADOPTED_VIEWS``).

Toast, notification and undo
----------------------------
Version 1.8 (``pk_toast``): the page's one toast, hosted by
``bemade_portal_kit.pk_toast_host`` (variable ``pk_notification``). Exports
``showToast(message, actionLabel, action, duration, {title, tone})``,
``keepClearOfToast(el, {fitOnly})``, ``offerUndos()``, ``bootToasts()``,
``UNDO_MS`` (8 s), ``NOTIFY_SHOWN_KEY`` and ``UNDO_OFFERS``. Other scripts
ask for a toast with the event ``pk:toast`` (``{message, actionLabel,
action, duration, title, tone}``). Markers: ``data-pk-toast-tone``,
``data-pk-toast-action`` (the action button), ``body[data-pk-toast-room]``.
The pk_fetch errors and offline / back online are toasts too.

* Session notification: a POST route stores ``session['notification']``
  (``{type, title, message}``); the next page's controller passes
  ``PortalKitApp._pk_pop_notification()`` as ``pk_notification`` (popped,
  a one-time id, the page not stored by the browser; a fragment request
  leaves it, a guard probe peeks). On load it shows once (never on back /
  forward, never twice for one id: storage key ``pk_notify_shown:v1``; a
  list under the former ``sc_notify_shown:v1`` key is moved once). Markers
  ``data-pk-notify``, ``-notify-title``, ``-notify-tone``, ``-notify-id``.
* Archive undo: ``PortalKitApp._pk_offer_undo(message, undo_url)`` (a
  same-site POST route that restores): the toast's « Undo » posts the
  hidden ``form[data-pk-undo]`` of the host.
* Undo offers: a hidden ``form[data-pk-undo-offer="<kind>"]`` with
  ``data-pk-toast-message``, ``data-pk-toast-action``, optional
  ``data-pk-undo-ms`` and ``data-pk-undo-param`` (a URL parameter dropped
  so a reload does not offer it again) is offered once on load; its toast's
  action submits it. Optional hooks per kind in the JS registry
  ``pk_undo_offers``: ``{rewriteUrl(url, form), after({form, root})}``.

Edit cards, sheets, tabs, lazy load and clamps
----------------------------------------------
Version 1.9 (scripts ``pk_edit_cards``, ``pk_sheets``, ``pk_tabs``,
``pk_clamp`` and ``pk_shell``; templates ``pk_edit_card_head``,
``pk_display_row``, ``pk_sheet`` and ``pk_page_tabs``, adopted from the
first consumer like the 1.5 templates):

* Edit cards: ``[data-pk-edit-card]`` with a read view
  (``data-pk-edit-view="read"``) and an edit view (``="edit"``). ONE pencil
  (``data-pk-edit-toggle``) opens it; while open (``data-pk-edit-open``)
  the pencil is a ✓ (``o_pk_edit_toggle_done``,
  ``data-pk-edit-toggle-done``; its label is ``data-pk-edit-done-label`` on
  the shell root, else the kit's) that closes it like « Done »
  (``data-pk-edit-done``). Edit-only controls: ``data-pk-edit-only``; a
  control outside its card names it with ``data-pk-edit-for``.
  ``data-pk-edit-open-on-load`` opens a card on load; the event
  ``pk:edit-open`` from inside a card opens it. Export:
  ``setCardEditing(card, editing)``. A link to ``#<details id>`` opens that
  ``<details>``.
* Read views: ``[data-pk-display="model:id:field"]`` takes a save's display
  in place (``pk:saved``); ``data-pk-display-hide-empty`` hides its holder
  while empty. Render helpers (``tools/display.py``, pure):
  ``pk_display(record, field)``, ``pk_display_key(record, field)``,
  ``pk_contact_href(kind, value)``; a consumer passes them to its templates
  under these names (``pk_display_row`` needs them).
* Sheets (``pk_sheet``: ``sheet_id``, ``title``, ``lazy_url``,
  ``lazy_fresh``, ``open_on_load``, ``head_extra``): openers
  ``data-pk-sheet-open="<id>"`` (``data-pk-sheet-url``: that body, fresh),
  ``data-pk-sheet-close``, ``data-pk-sheet-refetch`` (a link inside that
  reloads the body), ``data-pk-sheet-open-on-load``, a click on the
  backdrop closes. Export: ``openSheet(id)``.
* Lazy load: ``data-pk-lazy-url`` (a sheet, a ``<details>`` or a row's
  region), ``data-pk-lazy-fresh``, ``data-pk-lazy-filled`` (content without
  a link), ``data-pk-loaded``; a row's « Details »:
  ``data-pk-row-expand="<region id>"`` (``o_pk_row_open`` on its
  ``.o_pk_row_group``).
* Tabs (``pk_page_tabs``: ``tabs``, ``active``): ``data-pk-tabs``,
  ``data-pk-tab``, ``data-pk-tab-aliases``, ``data-pk-tab-panel``; ``?tab=``
  kept in the address, a ``#hash`` (or alias) opens its tab on load.
* Clamps: ``data-pk-clamp="N"`` (1 to 6 lines, the kit's CSS),
  ``data-pk-clamp-more``, ``-clamp-less``, ``-clamp-sep``, ``-clamp-meta``,
  ``-clamp-open``, ``-clamp-ready``.
* Shell boot (``pk_shell``): foreign drafts purged, ``data-pk-draft-clear``
  drops a prefix's drafts on load, the logout link clears every draft, the
  test database ribbon's height (``--pk-ribbon-h``).

Autosave field
--------------
Version 1.10: the shell's field (an OWL public component,
``bemade_portal_kit.pk_autosave_field``; template ``pk_field_autosave``,
adopted from the first consumer like the 1.5 templates), called with::

    <t t-call="bemade_portal_kit.pk_field_autosave">
        <t t-set="props" t-value="pk_field_props(record, 'name', label)"/>
    </t>

* Props builders (``tools/field_props.py``, pure; a consumer passes them to
  its templates under these names): ``pk_field_props(record, field, label,
  input_type='text', **extra)`` (server mode: saved through
  ``/my/app/save`` when the user leaves the field; input id
  ``pk_<model>_<id>_<field>``), ``pk_draft_props(draft_key, name, label,
  ...)`` (draft mode: a form field kept on the device under the caller's
  key, verbatim; input id ``pk_draft_<name>``), ``pk_form_props(target,
  label, ...)`` (form mode: written to the form's hidden input ``target``)
  and ``pk_options(pairs)``.
* Input types: ``text``, ``email``, ``tel``, ``textarea``, ``date`` (and
  the other date-like types: saved only once complete), ``date_na``,
  ``select``, ``segmented``, ``tags`` (option groups, ``groupSelect``).
* Behaviour: serialized saves, the 409 conflict banner (« Keep mine » /
  « Take theirs »; a 409 echoing this field's own value is not one), the
  offline queue replayed when back online, drafts restored / discarded,
  ``instant`` fields with « Undo » (``pk:toast``), sibling answers
  (``also``), the 428 confirm (the save spec's ``confirm`` hook answers
  ``{confirm: true, message, old, new[, detail]}``; « Confirm » re-posts with
  ``confirm=1``), ``lost_access`` (the page is left), ``pk:saved`` after a
  save, ``pk:form-reset`` honoured.
* Texts a consumer may pass (kit defaults in brackets): ``replace`` editor
  ``replaceCurrentLabel`` [Current text], ``replaceNewLabel`` [New text],
  ``replaceReuseLabel`` [Reuse current text]; group confirm
  ``groupConfirmMessage`` (« %s » = the dropped choices) [Changing this
  removes the other group's choices: %s.], ``groupConfirmLabel`` [Change],
  ``groupNotice`` [The choices of another group were removed.];
  ``savedLabel``, ``undoMessage``, ``historyLabel``, ``placeholder``,
  ``hint``.
* Markers: ``data-pk-autosave`` (mode), ``data-pk-autosave-field``,
  ``data-pk-autosave-state``, ``data-pk-autosave-restored`` on the root;
  ``data-pk-value``, ``data-pk-tags-open``, ``-tags-index``,
  ``-tags-typed-error``, ``-tags-group-notice``, ``data-pk-replace``,
  ``data-pk-group-confirm-box``, ``-group-cancel``, ``-group-confirm``
  inside; classes ``o_pk_replace_*``, ``o_pk_group_confirm*``,
  ``o_pk_confirm_banner``, ``-change``, ``-detail``, ``-ok``, ``-cancel``.
* Picker hook (a consumer's type-to-filter picker enhances the select):
  ``picker`` / ``pickerKey`` -> ``data-pk-picker`` / ``data-pk-picker-key``;
  ``optionMeta`` ``{value: {key: text}}`` -> ``data-pk-meta-<key>`` on each
  option.

App layout, user menu and shell components
------------------------------------------
Version 1.11 (task 5345). ``bemade_portal_kit.pk_app_layout`` is the shell
of every page of a portal app, on ``pk_frontend_layout``: the laptop rail
and phone tabs, the app bar (back chevron, home picto, logo, title and
context line, theme toggle, actions, user menu), the crumb trail of a
sub-page, the content (``main#pk_content``), the form guard's texts and the
toast host. A page calls it with its content as body::

    <t t-call="bemade_portal_kit.pk_app_layout">
        <t t-set="pk_title">Items</t>
        <t t-set="pk_active_nav" t-value="'items'"/>
        ...
    </t>

A consumer usually wraps it in its own layout that fills the slots once.

* Values (all optional): ``pk_title``, ``pk_active_nav``, ``pk_page_key``
  (the title and the crumb become the read fragments ``<key>:appbar`` /
  ``<key>:crumb``), ``pk_content_class``, ``pk_rail`` / ``pk_tabs`` (nav
  entries ``{key, url, icon, label}``, ``data-pk-nav-key``),
  ``pk_parent_url``, ``pk_crumbs`` (``[(label, url)]``), ``pk_context``
  (``portal.kit.pk_resolve``), ``pk_theme`` (``dark`` / ``light``, default
  light), ``pk_theme_choice`` + ``pk_pref_url`` (+ ``pk_theme_field``, the
  posted name, default ``pk_theme``; ``pk_current_url`` the redirect) for
  the theme toggle, ``pk_show_done`` (False: ``data-pk-hide-done``, the
  edit cards' « Done » buttons hidden), ``pk_edit_done_label``,
  ``pk_user_initials`` / ``_name`` / ``_role``, ``pk_settings_url`` (+
  ``pk_settings_active``), ``pk_home_url`` / ``pk_home_same_params``
  (``data-pk-home``), ``pk_db`` / ``pk_uid``, ``pk_guard_params`` (default
  ``error``), ``pk_notification``, ``pk_rendered_at`` and ``pk_brand``.
* Slots (``t-set`` bodies, empty by default): ``pk_head_extra``,
  ``pk_brand_mark`` (default: ``pk_brand_mark``, the kit's neutral mark),
  ``pk_appbar_actions`` (icons before the user menu),
  ``pk_user_menu_extra`` (items after « Settings ») and
  ``pk_layout_sheets`` (page-level sheets and dialogs, rendered after the
  content).
* Brand: ``portal.kit.pk_brand(overrides)`` = the hook ``_pk_brand()``
  (neutral defaults: the company name, ``/my``, « Home », the theme colours
  ``{light, dark}`` of the browser bar) with the page's ``pk_brand``
  merged over it.
* Markers: ``data-pk-top`` (``1`` on a top-level page),
  ``data-pk-hide-done``, ``data-pk-theme-color-light`` / ``-dark``,
  ``data-pk-user-menu``, ``data-pk-user-menu-head``, ``data-pk-pref`` (a
  preference form), ``data-pk-theme-toggle``, ``data-pk-theme-switch``,
  ``data-pk-theme-value``; ids ``pk_content``, ``pk_user_menu_bar``.
* Script ``pk_theme_pref``: a ``form[data-pk-pref]`` posts with fetch and
  applies the answer's ``pk_theme`` in place (export ``applyTheme(app,
  theme)``).
* ``pk_user_menu_popup`` (``pk_menu_id``): the user menu (adopted).

Components (adopted from the first consumer like the 1.5 templates):
``pk_entity_row`` (slot ``row_extra``), ``pk_link_row`` and
``pk_row_links`` (``data-pk-title-split``, ``-title-link``, ``-row-links``,
``-row-link``, ``-row-link-plain``), ``pk_list_header`` (``add_key`` ->
``data-pk-action``, ``data-pk-sort``), ``pk_card_icons`` (slot
``ci_extra``; ``ci_clock``, ``ci_archive``, ``ci_trash``, ``ci_editable``;
``data-pk-card-icons``, ``-card-archive``, ``-card-trash``,
``-activity-clock``, ``-activity-overdue``, ``o_pk_card_clock``),
``pk_history_entry`` / ``pk_history_list`` (``data-pk-history-state``,
``-scope``), ``pk_banner``, ``pk_flash_banners`` (``pk_flash``),
``pk_switch`` (``data-pk-switch-locked``, ``-switch-reason``),
``pk_confirm_sheet`` (``data-pk-confirm-submit``), ``pk_field_static`` and
``pk_overdue_flag`` (``o_pk_overdue``, ``data-pk-overdue``).

The app's pages and services (version 1.12)
--------------------------------------------
* Switch: Settings › Portal App (``bemade_portal_kit.enabled``;
  ``theme_choice_enabled``; ``help_home_url``), read with
  ``portal.kit._pk_shell_enabled()`` / ``_pk_shell_active(user)``. Off: the
  stock portal everywhere.
* Preferences: ``res.users.pk_theme`` (light / dark, default light; a
  consumer may change the field's default) and ``pk_show_done_buttons``,
  self-readable / -writeable; ``POST /my/app/pref`` writes the fields of
  ``portal.kit._pk_pref_fields()`` (and ``lang``) on the caller's own
  record (JSON ``{pk_theme, lang}`` or a same-site redirect).
* The controller ``PortalKitShell`` (``controllers/pk_shell.py``; a
  consumer's portal controller inherits it): ``_pk_shell_values(values,
  page, extra)`` (every value of ``pk_app_layout``, after the profile
  language guard ``_pk_profile_lang_guard``), the hook
  ``_pk_app_values(values, page)``, the pages ``/my/app/settings``
  (``pk_app_settings``, slot ``//t[@name='pk_settings_extra']``),
  ``/my/app/more`` (``pk_app_more``, the ``plus`` nav entries, slot
  ``//t[@name='pk_more_extra']``), ``/my/account`` and ``/my/security`` in
  the shell (``pk_app_account`` / ``pk_app_security``; phone rule
  ``portal.kit._pk_account_phone(phone, country)``), drawn on
  ``portal.kit._pk_layout()``.
* Language guard: a GET of a multilang page served in another language
  than the profile one is redirected once to its URL in the profile
  language; a ``multilang=False`` page (and any POST) is aligned in place,
  the ``frontend_lang`` cookie set to the profile language (version
  1.15.2).
* Help: the model ``portal.kit.help`` (key, url, sequence, active, note;
  Settings › Technical › Portal App Help), the hooks ``_pk_help_keys()``,
  ``_pk_help_page_key(page)``, ``_pk_help_tabbed()``, ``_pk_help_url(url)``;
  the app bar's « ? » (``data-pk-help``, ``pk_help.js``), the user menu's
  « Help » and « More »'s « User guide »; guide videos ``a.o_pk_video``
  (and the older ``a.o_fc_video`` of stored articles) through
  ``pk_guide_video.js``.
* Search: ``portal.kit._pk_search_providers()`` (``{key, title, search(words,
  limit, ctrl), available, sequence, url}``), ``_pk_search_placeholder()``,
  ``GET /my/app/search``, the sheet ``pk_search_sheet`` (``pk_search.js``:
  « / », Ctrl/⌘-K, arrows, Enter); the matching helpers ``pk_fold``,
  ``pk_words``, ``pk_name_matches`` (``tools/match.py``, ``pk_match.js``).
* Calendar: the OWL component ``bemade_portal_kit.pk_calendar``
  (``PkCalendar``; props ``feedUrl``, ``params``, ``locale``,
  ``detailKeys``, ``staffColors``, ``legendTitle``, ``showAllLabel``,
  ``unassignedLabel``, ``assigneeParam``), template ``pk_calendar``.
* Picker: ``pk_picker.js`` on ``select[data-pk-picker]``; declarative
  narrowing ``data-pk-picker-narrow="<parent key>:<meta key>"`` with
  ``data-pk-picker-hint``; ``data-pk-picker-scope``,
  ``data-pk-picker-empty`` (autosave field props ``pickerNarrow`` /
  ``pickerHint``).
* Data moves (``tools/data_moves.py``): the first consumer's user columns,
  parameters and help model are renamed in place by the install hook and
  both pre-migrations.

Kit addons (version 1.13)
-------------------------
``tools/adopt.adopt_views(cr, mapping, target)`` adopts views into another
module than the kit (``target``): a kit addon that takes over a consumer's
templates (e.g. ``bemade_portal_kit_pwa``, the installable app) uses it
from its own install hook. Version 1.14: ``tools/data_moves.move_columns(cr,
mapping, target)`` likewise moves a consumer's user column to a kit addon
(``bemade_portal_kit_dashboard``, the configurable dashboard).

Version guard (version 1.14.1)
------------------------------
``tools/version_guard.require_kit(cr, minimum, caller)``: the first statement
of a kit dependent's install hook or pre-migration. On a database whose kit
is older than ``PK_MIN_VERSION`` (``-u <consumer>`` alone upgrades
dependents, not the kit), it stops the run before anything is written and
says to upgrade the kit in the same run (``-u bemade_portal_kit,<consumer>``).
A fresh install, or the kit upgraded in the same run, is never blocked.

Notification preferences (version 1.17)
---------------------------------------
Each user chooses, per kind of notification, how the app e-mails them:
« Each message », « Daily digest » or « Never » (a kind offers a subset).
The kit only stores the choice; the addon that registers a kind sends its
notices (e.g. ``bemade_portal_kit_chat``).

* Hook ``portal.kit._pk_notification_kinds()`` -> ``[{'key', 'label',
  'modes', 'default', 'default_internal', 'app', 'sequence',
  'enabled'}]``: ``modes`` a subset of ``('each', 'digest', 'off')`` in
  display order, ``default`` for share (portal) users and
  ``default_internal`` for internal users (they have Discuss: usually
  ``off``), ``app`` (none: shared), ``enabled(kit, app)`` an optional gate
  (e.g. the feature is on for that app). Cached like the other
  registries: code only. Read with ``pk_notification_kinds(app=None)``.
* Model ``portal.kit.notification.pref`` (``user_id``, ``kind``,
  ``mode``; one row per user and kind, only once the user chose): each
  user reads and writes their own rows only.
* ``res.users._pk_notification_mode(kind)`` (the stored mode when the kind
  still allows it, else the default for that user) and
  ``users._pk_notification_users(kind, mode)`` (a batch: the users whose
  mode is ``mode``).
* « Settings › Notifications » (``#pk_notifications``, after the
  appearance, in the slot ``pk_settings_extra``'s place): one segmented
  control per kind (``data-pk-notify-pref="<kind>"``), shown only when the
  app has a kind. ``POST /my/app/notify-pref`` (``kind``, ``mode``,
  ``redirect``; CSRF): the caller's own row; an unknown kind or a mode the
  kind does not allow answers 400. JSON ``{kind, mode}`` for a fetch, else
  a same-site redirect.

Phone notifications (version 1.18)
----------------------------------
A kind that declares ``'push': True`` has a phone switch (« On the
phone », off by default) BESIDE its e-mail mode, not a fourth mode: the
addon that sends the kind's notices decides what a push replaces (the
chat: a pushed message skips its « each » e-mail, the digest still goes).
The kit sends nothing; ``bemade_portal_kit_pwa`` sends the pushes (Web
Push from the installed app, Odoo's own ``mail.push.device`` and keys).

* ``portal.kit._pk_push_available()``: False in the kit, True with
  ``bemade_portal_kit_pwa`` while the switch is on. The phone column shows
  only then, and only for the kinds that declare ``push``
  (``pk_notification_push_kinds(app)``).
* The switch is stored on the kind's ``portal.kit.notification.pref`` row
  (``push``; a row may hold the switch only, ``mode`` empty: the default
  mode applies). ``res.users._pk_notification_push(kind)``,
  ``users._pk_notification_push_users(kind)`` and
  ``res.users._pk_notification_push_partners(kind, partners)`` read it;
  ``users._pk_notification_set_push(kinds, value)`` writes it.
* ``POST /my/app/notify-pref`` takes ``push`` (``'1'`` / ``'0'``) with or
  instead of ``mode``: only for a kind that declares ``push`` while
  ``_pk_push_available()`` (else 400). JSON ``{kind, mode, push}``.
* « Settings › Notifications »: each phone-capable kind gets a switch
  (``form[data-pk-notify-push="<kind>"]``), and the section a device-state
  card (``[data-pk-push-state]``, one ``[data-pk-push-show]`` line per
  state: ``on``, ``off`` with the ``[data-pk-push-enable]`` button,
  ``denied``, ``ios-install``, ``unsupported``), filled in by the
  installed app's script.
* ``res.users.pk_push_prompted``: the one-time « get notified on this
  phone? » prompt was answered (it never comes back, on any device).
* ``portal.kit._pk_app_badge_count(user)``: the number on the installed
  app's icon (0 in the kit; the chat counts the unread messages).

Style guide
------------
``/pk/styleguide`` (internal users) shows every generic component with the
neutral slots; ``?theme=dark`` shows the dark theme.
""",
    'author': 'Bemade Inc.',
    'maintainers': ['dureposd'],
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/pk_security.xml',
        'views/pk_layout.xml',
        'views/pk_components.xml',
        'views/pk_styleguide.xml',
        # Task 5200 (P5): the kit's pages, account pages, calendar, back end.
        'views/pk_app_pages.xml',
        'views/pk_app_account.xml',
        'views/pk_calendar.xml',
        'views/pk_backend_views.xml',
    ],
    'assets': {
        # Task 5197 (P2): the shell's generic scripts. assets_frontend ONLY:
        # the lazy bundle includes this one, listing them there too would
        # bind them twice (tests/test_pk_assets.py).
        'web.assets_frontend': [
            # Task 5357 (P3b2): the shell's generic styles. One SCSS unit per
            # bundle, the kit's first: the consumers read $pk-* and override
            # the --pk-* slots.
            'bemade_portal_kit/static/src/scss/pk_variables.scss',
            'bemade_portal_kit/static/src/scss/pk_tokens.scss',
            'bemade_portal_kit/static/src/scss/pk_components.scss',
            'bemade_portal_kit/static/src/scss/pk_pages.scss',
            'bemade_portal_kit/static/src/scss/pk_calendar.scss',
            'bemade_portal_kit/static/src/scss/pk_account.scss',
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
            # Task 5199 (P4a): the screen refresh.
            'bemade_portal_kit/static/src/js/pk_fragments.js',
            # Task 5370 (P4b): the form guard, status pills and lazy edit.
            'bemade_portal_kit/static/src/js/pk_form_guard.js',
            'bemade_portal_kit/static/src/js/pk_status_pills.js',
            'bemade_portal_kit/static/src/js/pk_lazy_edit.js',
            # Task 5371 (P4c1): the toast, the notification and the undo.
            'bemade_portal_kit/static/src/js/pk_toast.js',
            # Task 5381 (P4c2): edit cards, sheets, tabs, clamps, boot.
            'bemade_portal_kit/static/src/js/pk_edit_cards.js',
            'bemade_portal_kit/static/src/js/pk_sheets.js',
            'bemade_portal_kit/static/src/js/pk_tabs.js',
            'bemade_portal_kit/static/src/js/pk_clamp.js',
            'bemade_portal_kit/static/src/js/pk_shell.js',
            # Task 5382 (P4c3): the autosave field (OWL component + template).
            'bemade_portal_kit/static/src/js/pk_autosave_field.js',
            'bemade_portal_kit/static/src/js/pk_theme_pref.js',
            'bemade_portal_kit/static/src/js/pk_autosave_field.xml',
            # Task 5200 (P5): name matching, picker, search, help, guide
            # videos, calendar (OWL), « My account ».
            'bemade_portal_kit/static/src/js/pk_match.js',
            'bemade_portal_kit/static/src/js/pk_picker.js',
            'bemade_portal_kit/static/src/js/pk_search.js',
            'bemade_portal_kit/static/src/js/pk_help.js',
            'bemade_portal_kit/static/src/js/pk_guide_video.js',
            'bemade_portal_kit/static/src/js/pk_calendar.js',
            'bemade_portal_kit/static/src/js/pk_calendar.xml',
            'bemade_portal_kit/static/src/js/pk_account.js',
        ],
        # The hoot unit tests (tests/test_pk_hoot.py runs them headless).
        # The modules they test are only DEFINED in the test page and run
        # per test file (hoot's lazy module loader).
        'web.assets_unit_tests_setup': [
            'bemade_portal_kit/static/src/js/pk_fetch.js',
            'bemade_portal_kit/static/src/js/pk_draft_store.js',
            'bemade_portal_kit/static/src/js/pk_confirm.js',
            'bemade_portal_kit/static/src/js/pk_app_nav.js',
            'bemade_portal_kit/static/src/js/pk_focus.js',
            'bemade_portal_kit/static/src/js/pk_list_header.js',
            'bemade_portal_kit/static/src/js/pk_user_menu.js',
            'bemade_portal_kit/static/src/js/pk_live_count.js',
            'bemade_portal_kit/static/src/js/pk_fragments.js',
            'bemade_portal_kit/static/src/js/pk_form_guard.js',
            'bemade_portal_kit/static/src/js/pk_status_pills.js',
            'bemade_portal_kit/static/src/js/pk_lazy_edit.js',
            'bemade_portal_kit/static/src/js/pk_toast.js',
            'bemade_portal_kit/static/src/js/pk_contact_href.js',
            'bemade_portal_kit/static/src/js/pk_edit_anchor.js',
            'bemade_portal_kit/static/src/js/pk_edit_cards.js',
            'bemade_portal_kit/static/src/js/pk_sheets.js',
            'bemade_portal_kit/static/src/js/pk_tabs.js',
            'bemade_portal_kit/static/src/js/pk_clamp.js',
            'bemade_portal_kit/static/src/js/pk_shell.js',
            'bemade_portal_kit/static/src/js/pk_date_bounds.js',
            'bemade_portal_kit/static/src/js/pk_autosave_field.js',
            'bemade_portal_kit/static/src/js/pk_theme_pref.js',
            'bemade_portal_kit/static/src/js/pk_autosave_field.xml',
            # Task 5200 (P5): name matching, picker, search, help, guide
            # videos, calendar (OWL), « My account ».
            'bemade_portal_kit/static/src/js/pk_match.js',
            'bemade_portal_kit/static/src/js/pk_picker.js',
            'bemade_portal_kit/static/src/js/pk_search.js',
            'bemade_portal_kit/static/src/js/pk_help.js',
            'bemade_portal_kit/static/src/js/pk_guide_video.js',
            'bemade_portal_kit/static/src/js/pk_calendar.js',
            'bemade_portal_kit/static/src/js/pk_calendar.xml',
            'bemade_portal_kit/static/src/js/pk_account.js',
        ],
        'web.assets_unit_tests': [
            'bemade_portal_kit/static/tests/**/*',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
}
