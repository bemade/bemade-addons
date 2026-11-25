# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5391: the kit scoped per app — two synthetic apps (« north »,
« south ») registered in one database, as two consumers installed side by
side would be.

Acceptance criteria:

* UC-A1 Per app, ``pk_match_url('/my/home')``, the crumbs
  (``pk_resolve``), the nav (``pk_visible_nav`` / ``pk_nav_labels`` /
  ``pk_nav_entries``), the pages (``pk_pages``), the search providers and
  the layout, preferences, help keys and search placeholder resolve to that
  app only; the shared entries (no app) appear in both; an app's own entry
  replaces a shared one of the same key for that app only. The
  declaration order does not matter: south's pages are declared first and
  a shared page also answers ``/my/home`` (the first-match bug of PR #623).
* UC-A2 A user holding roles in both apps gets one app, deterministically:
  the lowest ``sequence``, then the lowest key; the legacy ``'app': True``
  is the app ``default``, ``'app': False`` is no app.
* UC-A3 The default app: the system parameter when it names an app, else
  the only app, else the first one; a user without an app role reads it.
* UC-A4 Over HTTP, the kit's own page (« More ») draws each viewer's app's
  nav and crumbs only.
* UC-A5 Switch off: no app user is in the shell (the stock portal), as
  before.
Synthetic users, roles and pages only.
"""
from lxml import html as lxml_html

from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit.tools import Page, pk_nav, pk_static_page

from .common import pk_extra_roles, pk_frontend_langs, pk_hooks, pk_kit_shell

ROLES = {
    'n_member': {'groups': (), 'app': 'north'},
    's_member': {'groups': (), 'app': 'south'},
    'legacy': {'groups': (), 'app': True},
    'staff': {'groups': (), 'app': False},
}
ALL_ROLES = frozenset(ROLES)
# login -> roles (res.users._pk_extra_roles)
HOLDERS = {
    'pk_a_north': {'n_member'},
    'pk_a_south': {'s_member'},
    'pk_a_both': {'n_member', 's_member'},
    'pk_a_legacy': {'legacy'},
    'pk_a_staff': {'staff'},
}
APPS = {
    'north': {
        'sequence': 20,
        'layout': 'bemade_portal_kit.pk_app_layout',
        'pref_fields': {'north_pref': ('1', '0')},
        'help_keys': {'n_home': 'north-home'},
        'help_tabbed': ('north-home',),
        'search_placeholder': 'Search the north',
        'brand': {'name': 'North App'},
    },
    'south': {
        'sequence': 10,
        'layout': 'kit_test.south_layout',
    },
}


def _extra_roles(user):
    return frozenset(HOLDERS.get(user.login, ()))


def _nav(orig):
    return [
        pk_nav('s_tab', 'South Tab', 'home', '/kit/south', ALL_ROLES, 10, ('tab', 'rail'), app='south'),
        pk_nav('n_tab', 'North Tab', 'home', '/kit/north', ALL_ROLES, 10, ('tab', 'rail'), app='north'),
        pk_nav('shared', 'Shared Entry', 'more', '/kit/shared', ALL_ROLES, 50, ('tab', 'rail')),
        pk_nav('help', 'Help', 'help', '/kit/help', ALL_ROLES, 60, ('plus',)),
        pk_nav('help', 'North Help', 'help', '/kit/north-help', ALL_ROLES, 60, ('plus',), app='north'),
    ]


def _pages(orig):
    return list(orig) + [
        # Shared first, then south, then north: the order must not matter.
        pk_static_page('shared_home', '/my/home', 'Shared Home'),
        pk_static_page('s_home', '/my/home', 'South Home', app='south'),
        pk_static_page('s_sub', '/kit/south/sub', 'South Sub', parent=lambda v: ('s_home', {}), app='south'),
        pk_static_page('n_home', '/my/home', 'North Home', app='north'),
        pk_static_page('n_sub', '/kit/north/sub', 'North Sub', parent=lambda v: ('n_home', {}), app='north'),
        Page('both_sub', parent=lambda v: ('pk_app_more', {})),
        # North re-declares a kit page: for north only.
        pk_static_page('pk_app_settings', '/my/app/settings', 'North Settings',
                       parent=lambda v: ('n_home', {}), app='north'),
    ]


def _search(orig):
    return [
        {'key': 'north', 'title': 'North', 'search': lambda *a: [], 'url': '/kit/north', 'app': 'north'},
        {'key': 'south', 'title': 'South', 'search': lambda *a: [], 'app': 'south'},
        {'key': 'shared', 'title': 'Shared', 'search': lambda *a: []},
    ]


def _two_apps(env, apps=None):
    return pk_hooks(
        env,
        _pk_roles=lambda _orig: ROLES,
        _pk_apps=lambda _orig: apps if apps is not None else APPS,
        _pk_nav=_nav,
        _pk_pages=_pages,
        _pk_search_providers=_search,
    )


class AppsCommon:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)  # task 5392: the English texts asserted below
        cls.users = {
            login: new_test_user(cls.env, login=login, groups='base.group_portal', lang='en_US')
            for login in HOLDERS}
        cls.nobody = new_test_user(cls.env, login='pk_a_nobody', groups='base.group_portal')

    def setUp(self):
        super().setUp()
        shell = pk_kit_shell(self.env, roles=ROLES)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)
        apps = _two_apps(self.env)
        apps.__enter__()
        self.addCleanup(apps.__exit__, None, None, None)
        extra = pk_extra_roles(self.env, _extra_roles)
        extra.__enter__()
        self.addCleanup(extra.__exit__, None, None, None)
        self.params = self.env['ir.config_parameter'].sudo()
        self.params.set_param('bemade_portal_kit.default_app', False)

    def kit(self, login):
        user = self.users[login] if login in self.users else self.nobody
        return self.env['portal.kit'].with_user(user)


@tagged('post_install', '-at_install')
class TestPkApps(AppsCommon, TransactionCase):

    # ------------------------------------------------------------- UC-A1
    def test_home_and_crumbs_resolve_per_app(self):
        north, south = self.kit('pk_a_north'), self.kit('pk_a_south')
        self.assertEqual(north.pk_match_url('/my/home')[0], 'n_home')
        self.assertEqual(south.pk_match_url('/my/home')[0], 's_home')
        self.assertEqual(north.pk_resolve('n_sub', {})['crumbs'], [('North Home', '/my/home')])
        self.assertEqual(south.pk_resolve('s_sub', {})['crumbs'], [('South Home', '/my/home')])
        # A return URL to /my/home is the viewer's app's home.
        nav = north.pk_resolve('both_sub', {'return_url': '/my/home'})
        self.assertEqual(nav['crumbs'], [('North Home', '/my/home')])
        nav = south.pk_resolve('both_sub', {'return_url': '/my/home'})
        self.assertEqual(nav['crumbs'], [('South Home', '/my/home')])
        # Another app's page is unknown here (no crumb, never matched).
        self.assertIsNone(north.pk_match_url('/kit/south/sub'))
        self.assertEqual(north.pk_resolve('s_sub', {})['crumbs'], [])
        # An explicit app wins over the viewer's.
        self.assertEqual(north.pk_match_url('/my/home', app='south')[0], 's_home')

    def test_pages_per_app(self):
        north, south = self.kit('pk_a_north'), self.kit('pk_a_south')
        north_pages, south_pages = north.pk_pages(), south.pk_pages()
        self.assertIn('n_sub', north_pages)
        self.assertNotIn('s_sub', north_pages)
        self.assertIn('s_sub', south_pages)
        self.assertNotIn('n_sub', south_pages)
        for pages in (north_pages, south_pages):
            for key in ('pk_app_more', 'pk_app_account', 'both_sub', 'shared_home'):
                self.assertIn(key, pages)
        # The app's own pages first (they answer a URL before the shared ones).
        owners = [page.app for page in north_pages.values()]
        self.assertEqual(owners, ['north'] * 3 + [None] * (len(owners) - 3))
        self.assertEqual(set(list(north_pages)[:3]), {'n_home', 'n_sub', 'pk_app_settings'})
        # North's « Settings » replaces the kit's for north only.
        self.assertEqual(north_pages['pk_app_settings'].app, 'north')
        self.assertIsNone(south_pages['pk_app_settings'].app)
        self.assertEqual(north.pk_resolve('pk_app_account', {})['crumbs'],
                         [('North Home', '/my/home'), ('North Settings', '/my/app/settings')])
        self.assertEqual([label for label, _url in south.pk_resolve('pk_app_account', {})['crumbs']],
                         ['More', 'Settings'])

    def test_nav_per_app(self):
        north, south = self.kit('pk_a_north'), self.kit('pk_a_south')

        def keys(kit, roles, placement):
            return [entry['key'] for entry in kit.pk_visible_nav(roles, placement)]
        self.assertEqual(keys(north, {'n_member'}, 'tab'), ['n_tab', 'shared'])
        self.assertEqual(keys(south, {'s_member'}, 'tab'), ['s_tab', 'shared'])
        self.assertEqual(north.pk_nav_labels()['help'], 'North Help')
        self.assertEqual(south.pk_nav_labels()['help'], 'Help')
        self.assertNotIn('s_tab', north.pk_nav_labels())
        self.assertNotIn('n_tab', south.pk_nav_labels())
        self.assertEqual([entry['key'] for entry in north.pk_nav_entries()], ['n_tab', 'shared', 'help'])
        self.assertEqual(str(north.pk_nav_label('help')), 'North Help')
        self.assertEqual(str(north.pk_nav_label('s_tab', app='south')), 'South Tab')
        with self.assertRaises(KeyError):
            north.pk_nav_label('s_tab')

    def test_search_layout_and_hooks_per_app(self):
        north, south = self.kit('pk_a_north'), self.kit('pk_a_south')
        self.assertEqual([p['key'] for p in north.pk_search_providers()], ['north', 'shared'])
        self.assertEqual([p['key'] for p in south.pk_search_providers()], ['south', 'shared'])
        # pk_kit_shell patches _pk_layout: the kit's own resolution here.
        from odoo.addons.bemade_portal_kit.models.portal_kit import PortalKit
        self.assertEqual(PortalKit._pk_layout(north), 'bemade_portal_kit.pk_app_layout')
        self.assertEqual(PortalKit._pk_layout(south), 'kit_test.south_layout')
        self.assertIn('north_pref', PortalKit._pk_pref_fields(north))
        self.assertNotIn('north_pref', PortalKit._pk_pref_fields(south))
        self.assertEqual(north._pk_search_placeholder(), 'Search the north')
        self.assertEqual(south._pk_search_placeholder(), 'Search…')
        self.assertEqual(north._pk_help_page_key('n_home'), 'north-home')
        self.assertEqual(south._pk_help_page_key('n_home'), 'n_home')
        self.assertEqual(PortalKit._pk_help_tabbed(north), ('north-home',))
        self.assertEqual(PortalKit._pk_help_tabbed(south), ())
        self.assertEqual(north.pk_brand()['name'], 'North App')
        self.assertEqual(south.pk_brand()['name'], self.env.company.name)
        # A page's override still wins over the app's brand.
        self.assertEqual(north.pk_brand({'name': 'Page'})['name'], 'Page')

    # ------------------------------------------------------------- UC-A2
    def test_user_in_two_apps_gets_one(self):
        kit = self.env['portal.kit']
        both = self.users['pk_a_both']
        # south: sequence 10 < north's 20.
        self.assertEqual(kit._pk_app(both), 'south')
        self.assertEqual(self.kit('pk_a_both').pk_match_url('/my/home')[0], 's_home')
        with _two_apps(self.env, apps={'north': {'sequence': 1}, 'south': {'sequence': 10}}):
            self.assertEqual(kit._pk_app(both), 'north')
        # Same sequence: the lowest key.
        with _two_apps(self.env, apps={}):
            self.assertEqual(kit._pk_app(both), 'north')
        self.assertEqual(kit._pk_app(self.users['pk_a_legacy']), 'default')
        self.assertFalse(kit._pk_app(self.users['pk_a_staff']))
        self.assertFalse(kit._pk_app(self.nobody))
        self.assertFalse(kit._pk_app(self.env.ref('base.public_user')))
        self.assertEqual(kit.pk_app_roles(), frozenset({'n_member', 's_member', 'legacy'}))
        self.assertEqual(kit.pk_app_roles('north'), frozenset({'n_member'}))
        self.assertEqual(kit.pk_roles()['legacy']['app'], 'default')
        self.assertFalse(kit.pk_roles()['staff']['app'])

    # ------------------------------------------------------------- UC-A3
    def test_default_app(self):
        kit = self.env['portal.kit']
        # Three apps (default, north, south): the first by sequence.
        self.assertEqual(kit.pk_apps(), ['south', 'north', 'default'])
        self.assertEqual(kit._pk_default_app(), 'south')
        self.params.set_param('bemade_portal_kit.default_app', 'north')
        self.assertEqual(kit._pk_default_app(), 'north')
        # A user without an app role reads the default app.
        self.assertEqual(self.kit('pk_a_staff').pk_match_url('/my/home')[0], 'n_home')
        self.params.set_param('bemade_portal_kit.default_app', 'nowhere')
        self.assertEqual(kit._pk_default_app(), 'south')
        with pk_hooks(self.env, _pk_roles=lambda _orig: {'n_member': ROLES['n_member']},
                      _pk_apps=lambda _orig: {}):
            self.assertEqual(kit._pk_default_app(), 'north', 'the only app')
        with pk_hooks(self.env, _pk_roles=lambda _orig: {}, _pk_apps=lambda _orig: {}):
            self.assertFalse(kit._pk_default_app())
            # No app: the shared entries only.
            self.assertEqual(self.kit('pk_a_staff').pk_match_url('/my/home')[0], 'shared_home')

    # ------------------------------------------------------------- UC-A5
    def test_switch_off_no_app_user_in_the_shell(self):
        kit = self.env['portal.kit']
        for login in ('pk_a_north', 'pk_a_south', 'pk_a_both', 'pk_a_legacy'):
            self.assertTrue(kit._pk_shell_active(self.users[login]), login)
        self.assertFalse(kit._pk_shell_active(self.users['pk_a_staff']))
        self.params.set_param('bemade_portal_kit.enabled', 'False')
        for login in HOLDERS:
            self.assertFalse(kit._pk_shell_active(self.users[login]), login)


@tagged('post_install', '-at_install')
class TestPkAppsHttp(AppsCommon, HttpCase):

    def _tree(self, login, url):
        self.authenticate(login, login)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200, url)
        return response, lxml_html.document_fromstring(response.text)

    # ------------------------------------------------------------- UC-A4
    def test_more_page_draws_the_viewers_app(self):
        response, _tree = self._tree('pk_a_north', '/my/app/more')
        self.assertIn('North Tab', response.text)
        self.assertIn('Shared Entry', response.text)
        self.assertIn('North Help', response.text)
        self.assertNotIn('South Tab', response.text)
        response, _tree = self._tree('pk_a_south', '/my/app/more')
        self.assertIn('South Tab', response.text)
        self.assertIn('Shared Entry', response.text)
        self.assertNotIn('North Tab', response.text)
        self.assertNotIn('North Help', response.text)

    def test_settings_crumbs_follow_the_viewers_app(self):
        _response, tree = self._tree('pk_a_north', '/my/app/settings')
        back = tree.xpath('//a[contains(@class, "o_pk_back")]/@href')
        self.assertEqual(back, ['/my/home'], 'north: Settings is under its home')
        _response, tree = self._tree('pk_a_south', '/my/app/settings')
        back = tree.xpath('//a[contains(@class, "o_pk_back")]/@href')
        self.assertEqual(back, ['/my/app/more'], 'south: the kit\'s Settings, under « More »')

    def test_switch_off_stock_portal(self):
        self.params.set_param('bemade_portal_kit.enabled', 'False')
        self.authenticate('pk_a_north', 'pk_a_north')
        response = self.url_open('/my/app/more', allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.assertTrue(response.headers['Location'].endswith('/my/home'))
        response = self.url_open('/my/home')
        self.assertNotIn('data-pk-app-shell', response.text)
