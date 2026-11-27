"""Task 1795 — the Fit Crew client app: the kit app of every portal user who
holds no clinic staff role. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-C1 A portal user with no clinic role holds the ``client`` role and is
  in the client app (``fitcrew_client``); ``/my/home`` (and ``/my``) is the
  client home on the Fit Crew layout (200): the greeting, the tabs
  « Accueil / Plus » (+ « Rendez-vous » with the bookings addon), the rail on
  a laptop, the shortcut to « Mon compte ».
* UC-C2 « Plus » lists Mon compte, Sécurité, Paramètres, Installer
  l'application and Se déconnecter; « Paramètres » shows no staff-only
  section (the daily summary).
* UC-C3 A staff member (coach, therapist) who is also a client — and any
  staff — is in the staff app (``fitcrew``), unchanged; never ``client``.
* UC-C4 An internal user without a clinic role never gets ``client``: the
  stock portal home and « Pas d'accès » (with « Mon compte ») on a clinic URL.
* UC-C5 A clinic URL gives the client « Pas d'accès » (403) with « Accueil »
  (``/my/home``), never the staff app.
* UC-C6 No clinic data reaches a client page: no team, player, staff
  navigation entry, search, activity clock or medical sheet.
* UC-C7 The installable app is the same identity: the client page links the
  default manifest (``/my/app.webmanifest``), id and start URL ``/my/home``;
  « Installer l'application » answers 200 for a client.
* UC-C8 Kit switch off: the client gets the stock portal home.
* UC-C9 The client home renders in French (fr_CA, website-aware).
"""
import json

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.sc_app_nav import SC_APP, SC_CLIENT_APP
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestClientApp1795(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.plain.write({'name': 'Casey Client'})
        # An internal user without any clinic role (UC-C4).
        cls.internal_plain = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Internal Nobody', 'login': 'pc.inobody@example.com',
            'password': 'pc-inobody-1795',
            'group_ids': [Command.set([env.ref('base.group_user').id])],
        })

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _kit(self, user):
        return self.env['portal.kit'].with_user(user)

    def _client_home(self):
        self._login_plain()
        return self._get('/my/home')

    # -- UC-C1 -----------------------------------------------------------
    def test_portal_user_is_client(self):
        self.assertIn('client', self.plain._pk_roles())
        self.assertEqual(self._kit(self.plain)._pk_app(self.plain), SC_CLIENT_APP)
        self.assertIn('client', self.env['portal.kit'].pk_app_roles())

    def test_client_home(self):
        text, tree = self._client_home()
        shell = self._shell(tree)
        self.assertIsNotNone(shell)
        self.assertEqual(shell.get('data-pk-app-key') or SC_CLIENT_APP, SC_CLIENT_APP)
        self.assertTrue(tree.xpath('//*[@data-pk-section="client.greeting"]'))
        self.assertIn('Hello, Casey', ' '.join(text.split()))
        tabs = self._nav_keys(tree, 'o_pk_tabs')
        self.assertEqual(tabs[0], 'home')
        self.assertEqual(tabs[-1], 'more')
        self.assertEqual(self._nav_keys(tree, 'o_pk_rail_nav')[0], 'home')
        self.assertTrue(tree.xpath('//a[@data-sc-action="client.account"][@href="/my/account"]'))
        # The Fit Crew brand.
        self.assertIn('Le Fit Crew', text)
        self.assertTrue(tree.xpath('//img[contains(@src, "sc_logo_mark")]'))
        self.assertNotIn('o_portal_my_home', text)
        # /my too.
        _text, tree = self._get('/my')
        self.assertTrue(tree.xpath('//*[@data-pk-section="client.greeting"]'))

    # -- UC-C2 -----------------------------------------------------------
    def test_more_and_settings(self):
        self._login_plain()
        _text, tree = self._get('/my/app/more')
        keys = tree.xpath('//a[@data-pk-nav-key]/@data-pk-nav-key')
        for key in ('account', 'security', 'settings', 'install', 'logout'):
            self.assertIn(key, keys)
        self.assertTrue(tree.xpath('//a[@data-pk-nav-key="logout"][starts-with(@href, "/web/session/logout")]'))
        for key in ('teams', 'players', 'events', 'timesheets', 'digests', 'backend', 'clinic'):
            self.assertNotIn(key, keys)
        _text, tree = self._get('/my/app/settings')
        self.assertFalse(tree.xpath('//*[@id="sc_morning_summary"]'))
        for url in ('/my/account', '/my/security', '/my/app/install', '/my/app/dashboard/configure'):
            _text, tree = self._get(url)
            self.assertIsNotNone(self._shell(tree), url)

    def test_staff_settings_keep_the_daily_summary(self):
        self._login_tp()
        _text, tree = self._get('/my/app/settings')
        self.assertTrue(tree.xpath('//*[@id="sc_morning_summary"]'))

    # -- UC-C3 -----------------------------------------------------------
    def test_staff_never_client(self):
        for user in (self.coach, self.tp):
            self.assertNotIn('client', user._pk_roles())
            self.assertEqual(self._kit(user)._pk_app(user), SC_APP)

    def test_staff_row_role_is_not_client(self):
        """A portal user whose only clinic role comes from a staff row
        (head therapist) is staff, not a client."""
        self.env['sports.team.staff'].create({
            'team_id': self.team_a.id, 'partner_id': self.plain.partner_id.id, 'role': 'head_therapist'})
        roles = self.plain._pk_roles()
        self.assertIn('head_therapist', roles)
        self.assertNotIn('client', roles)

    def test_staff_and_client_gets_staff_app(self):
        """Both roles (a later catch-all sharing a user): the staff app wins
        (lower sequence)."""
        kit = self._kit(self.tp)
        self.assertLess(kit._pk_app_order(SC_APP), kit._pk_app_order(SC_CLIENT_APP))
        self._login_tp()
        _text, tree = self._get('/my/home')
        self.assertIn('teams', self._nav_keys(tree, 'o_pk_tabs'))
        self.assertFalse(tree.xpath('//*[@data-pk-section="client.greeting"]'))

    # -- UC-C4 -----------------------------------------------------------
    def test_internal_roleless_unchanged(self):
        self.assertNotIn('client', self.internal_plain._pk_roles())
        self.assertFalse(self._kit(self.internal_plain)._pk_app(self.internal_plain))
        self.authenticate('pc.inobody@example.com', 'pc-inobody-1795')
        resp = self.url_open('/my/teams')
        self.assertEqual(resp.status_code, 403)
        tree = lxml_html.fromstring(resp.text)
        self.assertTrue(tree.xpath('//a[@data-sc-action="no_access.account"][@href="/my"]'))
        self.assertFalse(tree.xpath('//a[@data-sc-action="no_access.home"]'))

    # -- UC-C5 -----------------------------------------------------------
    def test_clinic_url_no_access_with_home(self):
        self._login_plain()
        for url in ('/my/teams', '/my/players', '/my/clinics', '/my/team?team_id=%s' % self.team_a.id):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 403, url)
            tree = lxml_html.fromstring(resp.text)
            self.assertTrue(tree.xpath('//*[@data-sc-no-access-page]'), url)
            self.assertTrue(tree.xpath('//a[@data-sc-action="no_access.home"][@href="/my/home"]'), url)
            self.assertFalse(tree.xpath('//a[@data-sc-action="no_access.account"]'), url)
            self.assertNotIn('PC Team A', resp.text, url)

    # -- UC-C6 -----------------------------------------------------------
    def test_no_clinic_data_on_client_pages(self):
        self._login_plain()
        for url in ('/my/home', '/my/app/more', '/my/app/settings'):
            text, tree = self._get(url)
            for name in ('PC Team A', 'PC Team B', 'Pat', 'PC Coach', 'PC TP'):
                self.assertNotIn(name, text, '%s on %s' % (name, url))
            self.assertFalse(tree.xpath('//*[@data-sc-activity-clock-bar]'), url)
            self.assertFalse(tree.xpath('//*[@id="sc_injury_resolve_sheet"]'), url)
            self.assertFalse(tree.xpath('//*[@id="sc_proposal_sheet"]'), url)
            self.assertFalse(tree.xpath('//a[@href="/my/teams" or @href="/my/players"]'), url)
            self.assertFalse(tree.xpath('//*[contains(@class, "o_pk_search")][@data-pk-search]'), url)

    # -- UC-C7 -----------------------------------------------------------
    def test_same_installed_app(self):
        _text, tree = self._client_home()
        self.assertEqual(tree.xpath('//link[@rel="manifest"]/@href'), ['/my/app.webmanifest'])
        manifest = json.loads(self.url_open('/my/app.webmanifest').text)
        self.assertEqual(manifest['id'], '/my/home')
        self.assertEqual(manifest['start_url'], '/my/home')
        pwa = self._kit(self.plain)._pk_pwa(SC_CLIENT_APP)
        self.assertEqual((pwa['id'], pwa['start_url'], pwa['manifest_url']),
                         ('/my/home', '/my/home', '/my/app.webmanifest'))
        # Staff: the same manifest.
        self._login_tp()
        _text, tree = self._get('/my/home')
        self.assertEqual(tree.xpath('//link[@rel="manifest"]/@href'), ['/my/app.webmanifest'])

    # -- UC-C8 -----------------------------------------------------------
    def test_switch_off_stock_portal(self):
        self._switch(False)
        self._login_plain()
        text, tree = self._get('/my/home')
        self.assertIn('o_portal_my_home', text)
        self.assertIsNone(self._shell(tree))


@tagged('post_install', '-at_install')
class TestClientAppI18n1795(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_portal_kit', 'bemade_portal_kit_pwa', 'bemade_portal_kit_dashboard',
             'bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.plain.write({'lang': 'fr_CA', 'name': 'Casey Client'})

    def _fr(self, url, status=200):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, status, url)
        return ' '.join(resp.text.replace('&#39;', "'").split())

    # -- UC-C9 -----------------------------------------------------------
    def test_client_pages_in_french(self):
        self._switch(True)
        self._login_plain()
        text = self._fr('/my/home')
        for term in ('Accueil', 'Plus', 'Bonjour, Casey', 'Raccourcis', 'Mon compte',
                     'votre espace Fit Crew'):
            self.assertIn(term, text, term)
        for english in ('>Home<', 'Hello', 'Shortcuts', 'Welcome to your'):
            self.assertNotIn(english, text, english)
        text = self._fr('/my/app/more')
        for term in ('Mon compte', 'Sécurité', 'Paramètres', "Installer l'application", 'Se déconnecter'):
            self.assertIn(term, text, term)
        text = self._fr('/my/teams', status=403)
        self.assertIn('Pas d', text)
        self.assertIn('>Accueil<', text)
