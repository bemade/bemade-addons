"""Task 1542 — installable app (manifest, service worker, offline page,
« Installer l'application ») and the UI quality gates. Synthetic fixtures.

Task 5201 (kit P6): the installable app is bemade_portal_kit_pwa's (its
generic behaviour is tested there: switch, headers, worker, offline page,
install page, page script). The clinic keeps Fit Crew's app:

* UC-P1 (AC1) Switch OFF: the manifest, the worker and the offline page
  answer 404; the install page redirects.
* UC-P2 (AC5) Switch ON: the manifest is the « Le Fit Crew » app, exactly as
  before the move — name, short name, id = start_url = /my/home, scope /,
  standalone, Minuit colours, shortcuts Teams / Players; its icons are
  Fit Crew's PNGs, byte for byte (the company fields the clinic filled).
* UC-P3 The Fit Crew values fill only EMPTY fields: an administrator's edit
  survives the next upgrade (``sc_fill_pwa_branding``).
* UC-P4 (AC5) The offline page carries no user data and keeps Fit Crew's
  wording and colours.
* UC-P5 (AC5) « Plus › Installer l'application » is listed for every app
  role with Fit Crew's subtitle and renders the Fit Crew wording; no install
  banner anywhere else; the shell layout (only) links the manifest and the
  apple-touch-icon.
* UC-P6 (AC6) Lint: no ir.ui.view whose key starts with
  ``bemade_sports_clinic.sc_`` contains ``<script`` or ``style=``.
* UC-P7 (AC6) Assets: no ``sc_*`` file of this addon is listed in
  web.assets_frontend_lazy (it includes web.assets_frontend: a second
  listing would bind twice); the page script is the kit addon's (no clinic
  alias: two register scripts would both run).
"""
import base64
import json
import re

from lxml import html as lxml_html

from odoo.modules.module import get_manifest
from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.bemade_sports_clinic.models.sc_app_pwa import SC_PWA_ICONS, SC_PWA_IMG, sc_fill_pwa_branding
from odoo.addons.bemade_sports_clinic.models.sc_app_nav import SC_APP
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

PWA_URLS = ('/my/app.webmanifest', '/my/service-worker.js', '/my/app/offline')
# The URL name of each company icon field (bemade_portal_kit_pwa).
ICON_URLS = {
    'pk_pwa_icon_192': '/my/app/icon/icon-192.png',
    'pk_pwa_icon_512': '/my/app/icon/icon-512.png',
    'pk_pwa_icon_maskable_512': '/my/app/icon/icon-maskable-512.png',
    'pk_pwa_apple_touch_icon': '/my/app/icon/apple-touch-icon.png',
    'pk_pwa_logo': '/my/app/icon/logo.png',
}


def _png(filename):
    with file_open(SC_PWA_IMG + filename, 'rb') as source:
        return source.read()


@tagged('post_install', '-at_install')
class TestAppShellPwa1542(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # As the clinic's install / upgrade leaves the company (a test may
        # run on a database whose fields were emptied or edited).
        cls.env.company.write(dict.fromkeys([f for f, _n in SC_PWA_ICONS] + [
            'pk_pwa_name', 'pk_pwa_short_name', 'pk_pwa_background_color', 'pk_pwa_theme_color'], False))
        sc_fill_pwa_branding(cls.env)

    # -- UC-P1 -----------------------------------------------------------
    def test_switch_off_404(self):
        for url in PWA_URLS:
            resp = self.url_open(url, allow_redirects=False)
            self.assertEqual(resp.status_code, 404, url)
        self._login_tp()
        for url in PWA_URLS:
            resp = self.url_open(url, allow_redirects=False)
            self.assertEqual(resp.status_code, 404, url)
        resp = self.url_open('/my/app/install', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))

    # -- UC-P2 -----------------------------------------------------------
    def test_manifest_is_fit_crew(self):
        self._switch(True)
        # Task 5391: the public manifest is the database's default app — Fit
        # Crew's (named, should another consumer share the database).
        self.env['ir.config_parameter'].sudo().set_param('bemade_portal_kit.default_app', SC_APP)
        resp = self.url_open('/my/app.webmanifest', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/manifest+json', resp.headers['Content-Type'])
        manifest = json.loads(resp.text)
        labels = self.env['portal.kit'].pk_nav_labels(app=SC_APP)
        self.assertEqual({key: manifest[key] for key in manifest if key != 'icons'}, {
            'name': 'Le Fit Crew',
            'short_name': 'Fit Crew',
            'id': '/my/home',
            'start_url': '/my/home',
            'scope': '/',
            'display': 'standalone',
            'background_color': '#120e12',
            'theme_color': '#120e12',
            'shortcuts': [{'name': labels['teams'], 'url': '/my/teams'},
                          {'name': labels['players'], 'url': '/my/players'}],
        })
        purposes = {(icon['sizes'], icon['purpose']): icon['src'] for icon in manifest['icons']}
        self.assertEqual(set(purposes), {('192x192', 'any'), ('512x512', 'any'), ('512x512', 'maskable')})
        self.assertEqual(self.url_open(purposes[('192x192', 'any')]).content, _png('sc_icon_192.png'))
        self.assertEqual(self.url_open(purposes[('512x512', 'any')]).content, _png('sc_icon_512.png'))
        self.assertEqual(self.url_open(purposes[('512x512', 'maskable')]).content,
                         _png('sc_icon_maskable_512.png'))
        for field, filename in SC_PWA_ICONS:
            resp = self.url_open(ICON_URLS[field])
            self.assertEqual(resp.status_code, 200, field)
            self.assertEqual(resp.content, _png(filename), field)

    # -- UC-P3 -----------------------------------------------------------
    def test_fill_keeps_admin_edits(self):
        company = self.env.company
        company.write({'pk_pwa_short_name': 'Edited', 'pk_pwa_theme_color': '#000000',
                       'pk_pwa_logo': base64.b64encode(_png('sc_icon_192.png'))})
        self.assertEqual(sc_fill_pwa_branding(self.env), {}, 'nothing empty, nothing written')
        company.invalidate_recordset()
        self.assertEqual((company.pk_pwa_short_name, company.pk_pwa_theme_color), ('Edited', '#000000'))
        self.assertEqual(base64.b64decode(company.pk_pwa_logo), _png('sc_icon_192.png'))
        company.write({'pk_pwa_name': False, 'pk_pwa_icon_512': False})
        self.assertEqual(sc_fill_pwa_branding(self.env), {company.id: ['pk_pwa_icon_512', 'pk_pwa_name']})
        self.assertEqual(company.pk_pwa_name, 'Le Fit Crew')
        self.assertEqual(company.pk_pwa_short_name, 'Edited')

    # -- UC-P4 -----------------------------------------------------------
    def test_offline_page_carries_no_user_data(self):
        self._switch(True)
        self._login_tp()
        resp = self.url_open('/my/app/offline', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        for leak in ('PC TP', 'pc.tp@example.com', 'csrf_token', '__session_info__',
                     'session_info', '/web/assets/', 'PC Team A'):
            self.assertNotIn(leak, text, leak)
        self.assertIn('pk_offline.css', text)
        self.assertIn('href="/my/home"', text)
        self.assertIn('Le Fit Crew needs a connection to show teams and players.', text)
        tree = lxml_html.document_fromstring(text)
        self.assertEqual(tree.xpath('//title/text()'), ['Le Fit Crew'])
        self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#120e12'])
        style = tree.xpath('//body/@style')[0]
        for part in ('--pk-offline-bg: #120e12', '--pk-offline-accent: #a4c754', '--pk-offline-fg: #e5e5e5',
                     '--pk-offline-title-transform: uppercase'):
            self.assertIn(part, style)

    # -- UC-P5 -----------------------------------------------------------
    def test_install_entry_and_page(self):
        self._switch(True)
        for login in (self._login_coach, self._login_tp):
            login()
            text, tree = self._get('/my/app/more')
            entry = tree.xpath('//main//a[@data-pk-nav-key="install"]')
            self.assertTrue(entry)
            self.assertEqual(entry[0].get('href'), '/my/app/install')
            self.assertIn('Add Le Fit Crew to your home screen', text)
            text, tree = self._get('/my/app/install')
            self.assertIsNotNone(self._shell(tree))
            for key in ('ios', 'android', 'desktop'):
                self.assertTrue(tree.xpath('//*[@data-pk-install-steps="%s"]' % key), key)
            self.assertTrue(tree.xpath('//*[@data-pk-install-state="installed"][@hidden]'))
            self.assertEqual(tree.xpath('//button[@data-pk-install-prompt]/text()'), ['Install Le Fit Crew'])
            self.assertEqual(tree.xpath('//*[@data-pk-install]//strong/text()'), ['Le Fit Crew'])
            for term in ('Health data is never stored on the device.',
                         'no team or player data is kept on the device.',
                         'You are using Le Fit Crew from your home screen.'):
                self.assertIn(term, text, term)
            # The Fit Crew layout (the rail's brand).
            self.assertTrue(tree.xpath('//span[@class="o_pk_rail_brand_name"][text()="Le Fit Crew"]'))
        # Not on the tabs / rail, no banner on the home.
        _text, tree = self._get('/my/home')
        self.assertNotIn('install', self._nav_keys(tree, 'o_pk_tabs'))
        self.assertNotIn('install', self._nav_keys(tree, 'o_pk_rail_nav'))
        self.assertFalse(tree.xpath('//*[@data-pk-install]'))

    def test_manifest_links_in_shell_only(self):
        self._login_tp()
        text, _tree = self._get('/my/home')
        self.assertNotIn('/my/app.webmanifest', text)
        self.assertNotIn('/my/app/icon/', text)
        self._switch(True)
        _text, tree = self._get('/my/home')
        self.assertEqual(tree.xpath('//link[@rel="manifest"]/@href'), ['/my/app.webmanifest'])
        self.assertEqual(tree.xpath('//link[@rel="apple-touch-icon"][starts-with(@href, "/my/app/")]/@href'),
                         ['/my/app/icon/apple-touch-icon.png'])
        self.assertEqual(tree.xpath('//meta[@name="apple-mobile-web-app-title"]/@content'), ['Fit Crew'])
        self.assertTrue(tree.xpath('//meta[@name="apple-mobile-web-app-capable"]'))
        self.assertTrue(tree.xpath('//meta[@name="apple-mobile-web-app-status-bar-style"]'))

    # -- UC-P6 -----------------------------------------------------------
    def test_lint_no_inline_script_or_style_in_shell_views(self):
        views = self.env['ir.ui.view'].with_context(active_test=False).search(
            [('key', '=like', 'bemade_sports_clinic.sc_%')])
        self.assertTrue(views)
        offenders = []
        for view in views:
            arch = view.arch_db or ''
            if '<script' in arch.lower() or re.search(r'\sstyle\s*=', arch):
                offenders.append(view.key)
        self.assertFalse(offenders, 'inline <script> / style= in: %s' % offenders)

    # -- UC-P7 -----------------------------------------------------------
    def test_assets_no_double_binding(self):
        assets = get_manifest('bemade_sports_clinic')['assets']
        lazy = [path for path in assets.get('web.assets_frontend_lazy', [])
                if isinstance(path, str)]
        self.assertFalse([path for path in lazy if '/sc_' in path])
        frontend = assets['web.assets_frontend']
        self.assertTrue(any(path.endswith('sc_app_ui.js') for path in frontend))
        # Task 5201 (kit P6): the page script is the kit addon's, no alias.
        self.assertFalse([path for path in frontend if 'sw_register' in path])
        self.assertIn('bemade_portal_kit_pwa/static/src/js/pk_sw_register.js',
                      get_manifest('bemade_portal_kit_pwa')['assets']['web.assets_frontend'])
        # Task 5382 (kit P4c3): the autosave field is the kit's. Task 5345
        # (kit P3c2): its one-release alias key is gone, and the theme
        # preference script is the kit's (pk_theme_pref.js).
        for name in ('sc_autosave_field.js', 'sc_autosave_field.xml', 'sc_app_shell.js'):
            self.assertFalse([path for path in frontend if path.endswith(name)], name)
        kit_assets = get_manifest('bemade_portal_kit')['assets']['web.assets_frontend']
        for name in ('pk_autosave_field.js', 'pk_autosave_field.xml'):
            self.assertTrue(any(path.endswith(name) for path in kit_assets), name)
        # Task 5198 (P3a): the fetch helper is the kit's (no clinic alias).
        self.assertIn('bemade_portal_kit/static/src/js/pk_fetch.js', kit_assets)
        self.assertFalse([path for path in frontend if path.endswith('sc_fetch.js')])
        # No service worker in the clinic any more, bundled or not.
        bundled = [p for paths in assets.values() for p in paths if isinstance(p, str)]
        self.assertFalse([p for p in bundled if 'service_worker' in p or '/sw/' in p])
