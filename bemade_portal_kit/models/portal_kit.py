# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""``portal.kit`` — the per-database registries of the portal app shell.

Read this before adding a role, a menu entry, a visibility key or a page.

Hooks (extend them with ``super()`` in an ``_inherit = 'portal.kit'``)
-----------------------------------------------------------------------
* ``_pk_apps()``        ``{app: {...}}`` (task 5391: each app's layout,
  brand, home, installable app, preferences, help; see « Apps » below)
* ``_pk_roles()``       ``{role: {'groups': (xmlid, ...), 'app': key, ...}}``
* ``_pk_nav()``         ``[pk_nav(...), ...]``
* ``_pk_visibility()``  ``{key: {'include', 'exclude', 'system', 'model', 'field'}}``
* ``_pk_pages()``       ``[Page(...), ...]``
* ``_pk_save_specs()``  ``{model: spec}`` (task 5199: the save engine, see
  ``tools/save.py``; the kit declares ``mail.activity``)
* ``_pk_fragment_fillers()`` ``[callable(found, keys), ...]`` (task 5199:
  fill the fragments a render missed; never cached)
* ``_pk_activity_can_act(activity)`` / ``_pk_activity_assignable_users(activity)``
  (task 5199: the ``mail.activity`` spec's rules; per user, never cached)
* ``_pk_brand()``       ``{name, home_url, home_label, theme_colors}`` (task
  5345: the app layout's neutral brand; per company, never cached)
* Task 5200 (P5), never cached: ``_pk_layout()`` (the layout the kit's own
  pages are drawn on), ``_pk_pref_fields()`` (what /my/app/pref may write),
  ``_pk_account_phone(phone, country)`` (« My account »'s phone rule),
  ``_pk_help_keys()`` / ``_pk_help_tabbed()`` / ``_pk_help_url(url)`` (the
  in-app help), ``_pk_search_providers()`` / ``_pk_search_placeholder()``
  (the app bar's search). The switch: ``_pk_shell_enabled()`` /
  ``_pk_shell_active(user)``.
* ``_pk_notification_kinds()`` ``[{key, label, modes, default,
  default_internal, app?, sequence?, enabled?, push?}]`` (task 5516, kit
  1.17: the kinds of notification each user chooses a mode for, read
  through ``pk_notification_kinds(app)``; the kit registers none; task
  5546, kit 1.18: ``push`` gives a kind a phone switch)
* Task 5546 (kit 1.18), never cached: ``_pk_push_available()`` (phone
  notifications can be sent: ``bemade_portal_kit_pwa``) and
  ``_pk_app_badge_count(user)`` (the number on the installed app's icon)

Each hook is built ONCE per registry (``tools.ormcache``) and frozen: the
result is shared by every user and request of the database, so a hook holds
code only — never anything that depends on the user, a record or the
request. Per-user roles go in ``res.users._pk_extra_roles()`` (never
cached). An addon's entries live in its own class of this model, so they
exist only in the databases where it is installed (no module-level state).

An entry re-declared under an existing key (of the same app) replaces it in
place.

Apps (task 5391)
----------------
Several consumers may share one database (the bemade-addons CI installs
them all). Each declares an APP: a key on its roles (``'app': 'fitcrew'``;
``False``: not an app role; the legacy ``True`` is the app ``'default'``)
and on its entries (``pk_nav(..., app=)``, ``Page(..., app=)``,
``pk_dash_widget(..., app=)``, a search provider's ``'app'``). An entry
without an app is SHARED (the kit's Settings, More, Install, account…).

The viewer's app is ``_pk_app(user)``: the app of their app roles; a user
holding roles in several apps gets the app with the lowest ``sequence``
(``_pk_apps()``, default 100), then the lowest key. A user without an app
role reads the database's default app (``_pk_default_app()``: the system
parameter ``bemade_portal_kit.default_app`` when it names an app, else the
only app, else the lowest one by the same order); ``_pk_current_app()``
is that resolution for the current user. Every accessor (``pk_pages``,
``pk_match_url``, ``pk_resolve``, ``pk_visible_nav``, ``pk_nav_labels``,
``pk_nav_entries``, ``pk_search_providers``…) takes ``app=None`` (default:
``_pk_current_app()``) and sees the shared entries plus that app's own, an
own entry replacing a shared one of the same key; a URL matches the app's
own pages first. Save specs and visibility keys stay global (keyed by
model / key, checked against the roles).

``_pk_apps()`` registers each app (all keys optional)::

    {'fitcrew': {
        'sequence': 10,          # several apps for one user / no default
        'layout': 'module.tpl',  # the kit's own pages' layout
        'brand': {...} or callable(kit) -> {...},  # merged over _pk_brand()
        'home': 'module.tpl',    # the dashboard's home template (P7)
        'home_render': 'method', # or a controller method(values) drawing it
        'pref_fields': {field: allowed values},  # added to the kit's
        'help_keys': {page: help key}, 'help_tabbed': (help key, ...),
        'search_placeholder': str or lazy term,
        'pwa': {'start_url', 'manifest_id', 'shortcuts' (list or
                callable(kit)), 'offline_style' (dict or callable(kit, pwa))},
    }}

Hooks resolve PER APP, never per user: a consumer's override that answers
for its own app only tests the app (``self._pk_current_app()``), never the
user's groups, and calls ``super()`` for every other app.
"""
from urllib.parse import parse_qs, urlsplit

from odoo import _, api, models, tools
from odoo.tools.translate import LazyTranslate

from odoo.http import request

from ..tools import (
    Page, pk_activity_save_spec, pk_app_scoped, pk_freeze, pk_id_key, pk_is_visible,
    pk_refresh_patterns, pk_role_app, pk_safe_return_url, pk_static_page,
)
from ..tools.data_moves import MOVED_PARAMS

_lt = LazyTranslate(__name__)

# Task 5200 (P5): the app's system switch and theme choice.
PK_SHELL_PARAM = 'bemade_portal_kit.enabled'
PK_THEME_CHOICE_PARAM = 'bemade_portal_kit.theme_choice_enabled'
PK_HELP_HOME_PARAM = 'bemade_portal_kit.help_home_url'
# Task 5391: the database's default app (several apps in one database).
PK_DEFAULT_APP_PARAM = 'bemade_portal_kit.default_app'
PK_APP_SEQUENCE = 100
TRUTHY = ('1', 'true', 'yes', 'on')


def _by_key(items, key_of):
    """``{key: item}`` in first-declaration order, later items replacing."""
    result = {}
    for item in items:
        result[key_of(item)] = item
    return result


class PortalKit(models.AbstractModel):
    _name = 'portal.kit'
    _description = 'Portal Kit Registries'

    # ------------------------------------------------------------------
    # Hooks (consumers extend these with super())
    # ------------------------------------------------------------------
    @api.model
    def _pk_apps(self):
        """Task 5391: ``{app: spec}``, each app's registration (see « Apps »
        in the module docstring). Extend with ``super()``."""
        return {}

    @api.model
    def _pk_roles(self):
        return {}

    @api.model
    def _pk_nav(self):
        return []

    @api.model
    def _pk_visibility(self):
        return {}

    @api.model
    def _pk_pages(self):
        # Task 5200 (P5): the kit's own pages. « Settings » is a sub-page of
        # « More » (a consumer re-declares it under its home), « My account » / « Security »
        # sub-pages of « Settings » (no path: never a return URL), « More »
        # top level.
        return [
            pk_static_page('pk_app_more', '/my/app/more', _lt('More')),
            pk_static_page('pk_app_settings', '/my/app/settings', _lt('Settings'),
                           parent=lambda v: ('pk_app_more', {})),
            Page('pk_app_account', parent=lambda v: ('pk_app_settings', {})),
            Page('pk_app_security', parent=lambda v: ('pk_app_settings', {})),
        ]

    @api.model
    def _pk_save_specs(self):
        """Task 5199 (P4a): ``{model: spec}``, what the save route may write
        (``tools/save.py``). The kit declares ``mail.activity``."""
        return {'mail.activity': pk_activity_save_spec()}

    @api.model
    def _pk_fragment_fillers(self):
        """Task 5199 (P4a): ``[callable(found, keys)]``, run on a fragment
        answer: each may add to ``found`` (``{key: outer html}``) keys of
        ``keys`` the render did not carry. Not cached (cheap)."""
        return []

    @api.model
    def _pk_activity_can_act(self, activity):
        """Task 5199 (P4a): may the current user edit ``activity`` through
        the save route? Default: their own write right (ACL + rules)."""
        activity = activity.exists()
        return bool(activity) and activity.has_access('write')

    @api.model
    def _pk_activity_assignable_users(self, activity):
        """Task 5199 (P4a): the users ``activity`` may be assigned to by the
        current user. Default: the internal users and the user themself."""
        return self.env['res.users'].sudo().search([('share', '=', False)]) | self.env.user

    @api.model
    def _pk_brand(self):
        """Task 5345 (P3c2): the app layout's brand when a page passes none:
        the company's name, the portal home and the kit's theme colours
        (the browser bar of each theme: the neutral app-bar colour). Its
        mark is the kit's (``pk_brand_mark``) unless the page fills the
        layout's ``pk_brand_mark`` slot. Not cached (per company, language)."""
        return {
            'name': self.env.company.name or '',
            'home_url': '/my',
            'home_label': _('Home'),
            'theme_colors': {'light': '#ffffff', 'dark': '#020617'},
        }


    @api.model
    def _pk_notification_kinds(self):
        """Task 5516 (kit 1.17): the kinds of notification a user chooses a
        mode for (« Settings › Notifications »)::

            [{'key': 'chat.direct',          # unique, stored on the rows
              'label': _lt('Direct messages'),
              'modes': ('each', 'digest', 'off'),  # a subset, in order
              'default': 'each',             # share (portal) users
              'default_internal': 'off',     # internal users
              'app': None,                   # shared, or one app's
              'sequence': 10,
              'enabled': callable(kit, app) -> bool}]  # optional gate

        The kit registers none and sends nothing: the addon that registers
        a kind sends its notices, asking ``res.users._pk_notification_mode``
        / ``_pk_notification_users``. Extend with ``super()``.

        Task 5546 (kit 1.18): ``'push': True`` gives the kind a phone switch
        (« On the phone », off by default) beside its e-mail mode, read
        through ``res.users._pk_notification_push(kind)`` /
        ``_pk_notification_push_users`` / ``_pk_notification_push_partners``;
        shown while ``_pk_push_available()``."""
        return []

    @api.model
    def _pk_push_available(self):
        """Task 5546 (kit 1.18): can this database send phone notifications
        (Web Push from the installed app)? False in the kit;
        ``bemade_portal_kit_pwa`` answers True while the switch is on.
        Never cached."""
        return False

    @api.model
    def _pk_app_badge_count(self, user=None):
        """Task 5546 (kit 1.18): the number on the installed app's icon for
        ``user`` (default: the current user); 0 in the kit (the chat counts
        its unread messages). Extend with ``super()``; never cached."""
        return 0

    # ------------------------------------------------------------------
    # Task 5200 (P5): the switch, the preferences, the account, help, search
    # ------------------------------------------------------------------
    @api.model
    def _pk_param_true(self, key):
        """Is system parameter ``key`` truthy? An unset key reads the old key
        it was moved from (``tools/data_moves.MOVED_PARAMS``) for one
        release (the migration moves and deletes the old keys)."""
        get = self.env['ir.config_parameter'].sudo().get_param
        raw = get(key)
        if raw in (None, False):  # unset
            for old, new in MOVED_PARAMS:
                if new == key:
                    raw = get(old)
                    break
        return str(raw or '').strip().lower() in TRUTHY

    @api.model
    def _pk_shell_enabled(self):
        """The app's system switch (``bemade_portal_kit.enabled``,
        Settings › Portal App). Off: every page renders the stock portal."""
        return self._pk_param_true(PK_SHELL_PARAM)

    @api.model
    def _pk_shell_active(self, user=None):
        """The switch is on AND ``user`` (default: the current user) holds a
        role that puts them in an app."""
        if not self._pk_shell_enabled():
            return False
        return bool(self._pk_app(user))

    # ------------------------------------------------------------------
    # Task 5391: apps
    # ------------------------------------------------------------------
    @api.model
    def _pk_app_order(self, app):
        """The sort key of ``app``: its ``sequence``, then its key."""
        spec = self._pk_get_apps().get(app) or {}
        return (spec.get('sequence', PK_APP_SEQUENCE), app)

    @api.model
    def _pk_first_app(self, apps):
        """The first of ``apps`` (``_pk_app_order``), or False."""
        apps = [app for app in apps if app]
        return min(apps, key=self._pk_app_order) if apps else False

    @api.model
    def pk_apps(self):
        """Every app of the database: the apps of the roles and the
        registered ones, in order."""
        apps = {spec['app'] for spec in self._pk_get_roles().values() if spec['app']}
        apps.update(self._pk_get_apps())
        return sorted(apps, key=self._pk_app_order)

    @api.model
    def _pk_app(self, user=None):
        """The app of ``user`` (default: the current user): the app of
        their app roles (several: the first, ``_pk_app_order``), or False
        (no app role, the public user). Not cached across requests (roles
        are per user); memoised for the request being served."""
        user = user or self.env.user
        if user._is_public():
            return False
        memo = getattr(request, '_pk_app_memo', None) if request else None
        if not isinstance(memo, dict):  # none yet (or a test's mock request)
            memo = None
        if memo is not None and user.id in memo:
            return memo[user.id]
        roles = self._pk_get_roles()
        app = self._pk_first_app({
            roles[role]['app'] for role in user._pk_roles() if role in roles and roles[role]['app']})
        if request:
            if memo is None:
                memo = request._pk_app_memo = {}
            memo[user.id] = app
        return app

    @api.model
    def _pk_default_app(self):
        """The database's default app: ``bemade_portal_kit.default_app``
        when it names an app, else the only app, else the first one
        (``_pk_app_order``); False without any app. The public pages (the
        installable app's manifest) and the users without an app role read
        it."""
        apps = self.pk_apps()
        chosen = (self.env['ir.config_parameter'].sudo().get_param(PK_DEFAULT_APP_PARAM) or '').strip()
        if chosen in apps:
            return chosen
        return apps[0] if apps else False

    @api.model
    def _pk_current_app(self):
        """The app the current request is served in: the user's app, else
        the default app."""
        return self._pk_app() or self._pk_default_app()

    @api.model
    def _pk_home_url(self):
        """Task 5392: where ``/my`` and ``/my/home`` send the current user
        (without ``bemade_portal_kit_dashboard``, whose home is drawn there):
        for a user in an app (``_pk_shell_active``), the app's home, its
        brand's ``home_url`` (``_pk_apps()[app]['brand']``); False (the
        portal home) when that is ``/my`` or ``/my/home`` (the neutral
        brand) or not a same-site path, and for anyone else."""
        if not self._pk_shell_active():
            return False
        url = pk_safe_return_url(self.pk_brand().get('home_url'), False)
        if not url or urlsplit(url).path.rstrip('/') in ('/my', '/my/home'):
            return False
        return url

    @api.model
    def _pk_resolve_app(self, app=None):
        """``app``, else ``_pk_current_app()`` (the accessors' default)."""
        return app or self._pk_current_app()

    @api.model
    def pk_app_spec(self, app=None):
        """The registration of ``app`` (default: the current app), read-only
        (an empty mapping for an app that registers nothing)."""
        return self._pk_get_apps().get(self._pk_resolve_app(app)) or pk_freeze({})

    @api.model
    def _pk_theme_choice_enabled(self):
        """The users may choose their theme (``bemade_portal_kit.
        theme_choice_enabled``). Absent / off: everyone gets the default
        theme and the theme toggles are hidden; each user's saved theme
        stays and applies again once it is on."""
        return self._pk_param_true(PK_THEME_CHOICE_PARAM)

    @api.model
    def _pk_default_theme(self):
        """The default of ``res.users.pk_theme`` (the kit's: light; a
        consumer changes the field's default)."""
        return self.env['res.users'].default_get(['pk_theme']).get('pk_theme') or 'light'

    @api.model
    def _pk_effective_theme(self, user=None):
        """The theme the app renders for ``user``."""
        if not self._pk_theme_choice_enabled():
            return self._pk_default_theme()
        user = user or self.env.user
        return user.sudo().pk_theme or self._pk_default_theme()

    @api.model
    def _pk_layout(self):
        """The template the kit's own pages (settings, More, account,
        security) are drawn on: the current app's ``layout`` (task 5391),
        else the kit's app layout."""
        return self.pk_app_spec().get('layout') or 'bemade_portal_kit.pk_app_layout'

    @api.model
    def _pk_pref_fields(self):
        """``{field: allowed values}``: the ONLY ``res.users`` fields
        /my/app/pref may write on the caller's own record. A boolean field
        is posted as ``'1'`` / ``'0'``; ``None`` = the frontend languages
        (``lang``). The current app's ``pref_fields`` are added (task
        5391). Extend with ``super()``."""
        fields_ = {
            'pk_theme': ('light', 'dark'),
            'pk_show_done_buttons': ('1', '0'),
            'lang': None,
        }
        fields_.update(self.pk_app_spec().get('pref_fields') or {})
        return fields_

    @api.model
    def _pk_account_phone(self, phone, country=None):
        """« My account »'s phone as it is saved; raise ``ValidationError``
        (its message shown on the field) to refuse it. Kit: unchanged."""
        return phone

    @api.model
    def _pk_help_keys(self):
        """``{page key: help key}``: a page's key in the help mapping
        (``portal.kit.help``). A page not listed uses its own key."""
        return {
            'pk_app_settings': 'settings',
            'pk_app_more': 'home',
            'pk_app_account': 'account',
            'pk_app_security': 'account',
        }

    @api.model
    def _pk_help_page_key(self, page):
        """The help key of page ``page``: the current app's ``help_keys``
        (task 5391), else ``_pk_help_keys()``, else the page key itself
        (``home`` without a page)."""
        own = self.pk_app_spec().get('help_keys') or {}
        return own.get(page) or self._pk_help_keys().get(page) or page or 'home'

    @api.model
    def _pk_help_tabbed(self):
        """The help keys whose page refines the key with its active tab
        (« <key>.<tab> »): the « ? » follows the tab (``pk_help.js``): the
        current app's ``help_tabbed`` (task 5391)."""
        return tuple(self.pk_app_spec().get('help_tabbed') or ())

    @api.model
    def _pk_help_url(self, url):
        """The link a configured help URL opens, or False when it cannot be
        opened here. Kit: the URL itself."""
        return url

    @api.model
    def _pk_search_providers(self):
        """The app bar's search: ``[{'key', 'title', 'search', 'available',
        'sequence', 'url', 'app'}]`` (``app``, task 5391: the app it serves;
        none: every app). ``search(words, limit, ctrl)`` (``ctrl``: the
        portal controller serving the request, as the save specs get it)
        returns rows ``{'id',
        'title', 'subtitle', 'url', 'locked', 'archived', 'archived_label',
        'action_label', 'action_url', 'near', 'template'}`` (all optional but
        ``title``); ``available()`` (optional) says whether the current user
        may use the provider; ``url`` (optional) is the magnifier's link
        without JavaScript. No available provider: no magnifier."""
        return []

    @api.model
    def _pk_search_placeholder(self):
        """The search box's placeholder: the current app's
        ``search_placeholder`` (task 5391), else the kit's."""
        placeholder = self.pk_app_spec().get('search_placeholder')
        return str(placeholder) if placeholder else _("Search…")

    @api.model
    def pk_search_providers(self, app=None):
        """The providers of ``app`` (default: the current app) available to
        the current user, by sequence."""
        app = self._pk_resolve_app(app)
        providers = [p for p in pk_app_scoped(self._pk_search_providers(), app, lambda p: p['key'])
                     if not p.get('available') or p['available']()]
        return sorted(providers, key=lambda p: p.get('sequence', 10))

    @api.model
    def pk_help_home(self):
        """The help home (``bemade_portal_kit.help_home_url``), resolved."""
        get = self.env['ir.config_parameter'].sudo().get_param
        home = get(PK_HELP_HOME_PARAM)
        if home in (None, False):  # unset
            for old, new in MOVED_PARAMS:
                if new == PK_HELP_HOME_PARAM:
                    home = get(old)
        return (home or '').strip()

    # ------------------------------------------------------------------
    # Task 5516 (kit 1.17): notification preferences
    # ------------------------------------------------------------------
    @api.model
    def pk_notification_kinds(self, app=None):
        """The notification kinds of ``app`` (default: the current app):
        the shared ones and the app's own, by sequence, those whose
        ``enabled(kit, app)`` gate answers False left out. Read-only."""
        app = self._pk_resolve_app(app)
        kinds = pk_app_scoped(self._pk_get_notification_kinds(), app, lambda kind: kind['key'])
        kinds = [kind for kind in kinds if not kind.get('enabled') or kind['enabled'](self, app)]
        return sorted(kinds, key=lambda kind: kind.get('sequence', 10))

    @api.model
    def pk_notification_kind(self, key):
        """The kind ``key`` (any app; the first declared), or None."""
        for kind in self._pk_get_notification_kinds():
            if kind['key'] == key:
                return kind
        return None

    @api.model
    def pk_notification_mode_labels(self):
        """``{mode: label}`` in the request language."""
        return {
            'each': _("Each message"),
            'digest': _("Daily digest"),
            'off': _("Never"),
        }

    @api.model
    def pk_notification_rows(self, user=None, app=None):
        """« Settings › Notifications »: one row per kind of ``app``
        (default: the current app) for ``user`` (default: the current
        user): ``{key, label, modes: [(mode, label)], current, push}``;
        ``push`` (task 5546) is the phone switch of a kind that declares
        one while ``_pk_push_available()``, else None (no switch)."""
        user = user or self.env.user
        labels = self.pk_notification_mode_labels()
        push_on = self._pk_push_available()
        rows = []
        for kind in self.pk_notification_kinds(app):
            rows.append({
                'key': kind['key'],
                'label': str(kind['label']),
                'modes': [(mode, labels.get(mode, mode)) for mode in kind['modes']],
                'current': user._pk_notification_mode(kind['key']),
                'push': user._pk_notification_push(kind['key']) if push_on and kind.get('push') else None,
            })
        return rows

    @api.model
    def pk_notification_push_kinds(self, app=None):
        """Task 5546: the keys of the kinds of ``app`` (default: the current
        app) that have a phone switch (``'push': True``)."""
        return [kind['key'] for kind in self.pk_notification_kinds(app) if kind.get('push')]

    # ------------------------------------------------------------------
    # Cached, frozen registries (one per database registry)
    # ------------------------------------------------------------------
    @api.model
    @tools.ormcache()
    def _pk_get_apps(self):
        apps = {}
        for app, spec in self._pk_apps().items():
            spec = dict(spec)
            if isinstance(spec.get('pwa'), dict):
                spec['pwa'] = pk_freeze(spec['pwa'])
            apps[app] = pk_freeze(spec)
        return pk_freeze(apps)

    @api.model
    @tools.ormcache()
    def _pk_get_notification_kinds(self):
        """Every app's kinds, one per (app, key), frozen (task 5516)."""
        kinds = _by_key(self._pk_notification_kinds(), lambda kind: (kind.get('app') or None, kind['key']))
        return tuple(pk_freeze(dict(kind, modes=tuple(kind['modes']))) for kind in kinds.values())

    @api.model
    @tools.ormcache()
    def _pk_get_roles(self):
        roles = {}
        for role, spec in self._pk_roles().items():
            spec = dict(spec)
            spec['groups'] = tuple(spec.get('groups') or ())
            spec['app'] = pk_role_app(spec.get('app', True))
            roles[role] = pk_freeze(spec)
        return pk_freeze(roles)

    @api.model
    @tools.ormcache()
    def _pk_get_nav(self):
        """Every app's entries, one per (app, key), in declaration order."""
        entries = _by_key(self._pk_nav(), lambda entry: (entry.get('app') or None, entry['key']))
        return tuple(pk_freeze(entry) for entry in entries.values())

    @api.model
    @tools.ormcache('app')
    def _pk_get_app_nav(self, app):
        """The entries ``app`` sees (``pk_app_scoped``)."""
        return tuple(pk_app_scoped(self._pk_get_nav(), app, lambda entry: entry['key']))

    @api.model
    @tools.ormcache()
    def _pk_get_visibility(self):
        return pk_freeze({key: pk_freeze(spec) for key, spec in self._pk_visibility().items()})

    @api.model
    @tools.ormcache()
    def _pk_get_pages(self):
        """Every app's pages, one per (app, key): ``{(app, key): Page}``."""
        return pk_freeze(_by_key(self._pk_pages(), lambda page: (page.app, page.key)))

    @api.model
    @tools.ormcache('app')
    def _pk_get_app_pages(self, app):
        """``{key: Page}`` of the pages ``app`` sees, its own first (the
        order ``pk_match_url`` tries them in)."""
        pages = pk_app_scoped(list(self._pk_get_pages().values()), app, lambda page: page.key, own_first=True)
        return pk_freeze({page.key: page for page in self._pk_app_pages(app, pages)})

    @api.model
    def _pk_app_pages(self, app, pages):
        """Hook: the pages of ``app`` (a list, in match order) as the kit
        registers them; an addon may drop a shared page an app replaces (the
        dashboard's home for an app with its own). Cached per app."""
        return pages

    @api.model
    @tools.ormcache()
    def _pk_get_save_specs(self):
        return pk_freeze({model: pk_freeze(spec) for model, spec in self._pk_save_specs().items()})

    # ------------------------------------------------------------------
    # Save engine (task 5199)
    # ------------------------------------------------------------------
    @api.model
    def pk_save_specs(self):
        """``{model: spec}`` (read-only)."""
        return self._pk_get_save_specs()

    @api.model
    def pk_save_spec(self, model):
        """The save spec of ``model`` (read-only), or None."""
        return self._pk_get_save_specs().get(model)

    @api.model
    def pk_refresh_patterns(self, record, field):
        """The fragment key patterns a save of ``record.field`` makes stale."""
        return pk_refresh_patterns(self.pk_save_spec(record._name), record, field)

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------
    @api.model
    def pk_roles(self):
        """The declared roles (read-only)."""
        return self._pk_get_roles()

    @api.model
    def pk_app_roles(self, app=None):
        """The roles that put a user in an app (all but ``'app': False``);
        ``app`` given: that app's only."""
        return frozenset(role for role, spec in self._pk_get_roles().items()
                         if spec['app'] and (app is None or spec['app'] == app))

    # ------------------------------------------------------------------
    # Brand (task 5345)
    # ------------------------------------------------------------------
    @api.model
    def pk_brand(self, overrides=None, app=None):
        """The brand the app layout draws: ``_pk_brand()``, the ``brand`` of
        ``app`` (default: the current app; task 5391) and the page's
        ``overrides`` (a partial dict) merged over it in that order, the
        theme colours key by key. A new dict on every call."""
        brand = dict(self._pk_brand())
        colors = dict(brand.get('theme_colors') or {})
        app_brand = self.pk_app_spec(app).get('brand')
        if callable(app_brand):
            app_brand = app_brand(self)
        for layer in (app_brand, overrides):
            for key, value in (layer or {}).items():
                if key == 'theme_colors':
                    colors.update(value or {})
                elif value is not None:
                    brand[key] = value
        brand['theme_colors'] = colors
        return brand

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------
    @api.model
    def pk_is_visible(self, spec, roles):
        """``include`` any-of, ``exclude`` none-of; exclude wins."""
        return pk_is_visible(spec, roles)

    @api.model
    def pk_visibility(self):
        """The declared visibility keys (read-only)."""
        return self._pk_get_visibility()

    @api.model
    def pk_can(self, key, roles, is_system=False):
        """May this role set SEE ``key``? Unknown keys raise ``KeyError``
        (typos must fail loudly, not silently hide a section).
        ``is_system`` (the viewer is in ``base.group_system``) also opens
        the keys flagged ``system``, unless one of the roles is excluded."""
        spec = self._pk_get_visibility()[key]
        if is_system and spec.get('system'):
            return not frozenset(roles or ()) & frozenset(spec.get('exclude') or ())
        return pk_is_visible(spec, roles)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    @api.model
    def pk_nav_entries(self, app=None):
        """The nav entries of ``app`` (default: the current app; the shared
        ones included), read-only, in declaration order."""
        return self._pk_get_app_nav(self._pk_resolve_app(app))

    @api.model
    def pk_visible_nav(self, roles, placement, ctx=None, app=None):
        """The entries of ``app`` (default: the current app) visible to
        ``roles`` at ``placement``, by sequence. ``ctx`` feeds the entries'
        ``requires(ctx)`` gates."""
        ctx = ctx or {}
        entries = [
            entry for entry in self.pk_nav_entries(app)
            if placement in entry['placement']
            and pk_is_visible(entry, roles)
            and (entry.get('requires') is None or entry['requires'](ctx))
        ]
        return sorted(entries, key=lambda entry: entry['sequence'])

    @api.model
    def pk_nav_label(self, key, app=None):
        """The (lazy) label of nav entry ``key`` of ``app`` (default: the
        current app; a hook building a cached registry names its app);
        ``KeyError`` if unknown."""
        for entry in self.pk_nav_entries(app):
            if entry['key'] == key:
                return entry['label']
        raise KeyError(key)

    @api.model
    def pk_nav_labels(self, app=None):
        """``{key: label}`` of every nav entry of ``app`` (default: the
        current app), in the current language."""
        return {entry['key']: str(entry['label']) for entry in self.pk_nav_entries(app)}

    # ------------------------------------------------------------------
    # Pages: parent, back, crumbs, return URLs
    # ------------------------------------------------------------------
    @api.model
    def pk_pages(self, app=None):
        """``{key: Page}`` of ``app`` (default: the current app; the shared
        pages included), read-only, its own pages first."""
        return self._pk_get_app_pages(self._pk_resolve_app(app))

    @api.model
    def pk_safe_return_url(self, value, fallback, prefixes=None):
        """See ``tools.pk_safe_return_url``."""
        return pk_safe_return_url(value, fallback, prefixes=prefixes)

    @api.model
    def pk_match_url(self, url, app=None):
        """``(page_key, values)`` of the page of ``app`` (default: the
        current app) ``url`` points to, if the URL is a safe in-app path
        whose records the current user may read; else None. The app's own
        pages are tried before the shared ones."""
        url = pk_safe_return_url(url, None)
        if not url:
            return None
        parts = urlsplit(url)
        args = parse_qs(parts.query)
        for page in self.pk_pages(app).values():
            if not page.path or page.url is None:
                continue
            match = page.path.fullmatch(parts.path)
            if not match:
                continue
            values = page.from_url(self.env, match, args)
            if values is None:
                return None
            return page.key, values
        return None

    @api.model
    def _pk_trail(self, key, values, app=None):
        """[(label, url), …] from the top-level ancestor down to ``key``."""
        pages = self.pk_pages(app)
        trail = []
        seen = set()
        while key and key not in seen:
            seen.add(key)
            page = pages[key]
            label = str(page.label(values)) if page.label else ''
            trail.insert(0, (label, page.url(values)))
            parent = page.parent(values)
            key, values = parent if parent else (None, None)
        return trail

    @api.model
    def pk_resolve(self, key, values, request_url=None, request_return_url=None, app=None):
        """Navigation of page ``key`` rendered with ``values``.

        Returns ``{'parent_url', 'crumbs', 'context'}``: ``parent_url`` False
        on a top-level page; ``crumbs`` the ancestors, top first (the current
        page, the title, is appended by the layout); ``context`` the line
        under the title (shown with the back chevron)."""
        app = self._pk_resolve_app(app)
        page = self.pk_pages(app).get(key)
        if not page:
            return {'parent_url': False, 'crumbs': [], 'context': False}
        parent = page.parent(values)
        if parent is None:
            # Top level (logo): a return URL never adds a back chevron to a tab.
            return {'parent_url': False, 'crumbs': [],
                    'context': str(page.context(values) or '') if page.context else False}
        if page.return_url is not None:
            raw_return = page.return_url(values)
        elif 'return_url' in values:
            raw_return = values.get('return_url')
        else:
            raw_return = request_return_url
        matched = self.pk_match_url(raw_return, app=app) if raw_return else None
        if matched and request_url and pk_id_key(raw_return) == pk_id_key(request_url):
            matched = None  # a page is never its own parent
        if matched:
            crumbs = self._pk_trail(*matched, app=app)
            crumbs[-1] = (crumbs[-1][0], raw_return)
        else:
            crumbs = self._pk_trail(*parent, app=app)
        context = page.context(values) if page.context else None
        return {
            'parent_url': crumbs[-1][1],
            'crumbs': crumbs,
            'context': str(context) if context else crumbs[-1][0],
        }
