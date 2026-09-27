"""Task 1542 — installable app (manifest, service worker, offline page,
« Installer l'application ») and the UI quality gates. Synthetic fixtures.

Acceptance criteria covered here:

* UC-P1 (AC1) Switch OFF: /my/app.webmanifest, /my/service-worker.js and
  /my/app/offline answer 404 (the page script then unregisters the worker —
  browser-tested in test_app_shell_tours_1542); the install page redirects.
* UC-P2 (AC5) Switch ON: the manifest is the « Le Fit Crew » app — scope
  /my/, start_url /my/home, standalone, Minuit colours, 192 / 512 / maskable
  icons that exist, shortcuts; served without a website language redirect.
* UC-P3 (AC5) The service worker never caches a /my/ page or JSON: no
  run-time cache write at all, only the precache of the data-free offline
  page + static files; versioned cache name, old caches deleted; served with
  Service-Worker-Allowed /my/ and no-cache.
* UC-P4 (AC5) The offline page carries no user data (fetched logged in:
  no name, no login, no CSRF token, no session info, no asset bundle).
* UC-P5 (AC5) « Plus › Installer l'application » is listed for every app
  role and renders iOS / Android steps; no install banner anywhere else;
  the shell layout (only) links the manifest and the apple-touch-icon.
* UC-P6 (AC6) Lint: no ir.ui.view whose key starts with
  ``bemade_sports_clinic.sc_`` contains ``<script`` or ``style=``.
* UC-P7 (AC6) Assets: no ``sc_*`` file of this addon is listed in
  web.assets_frontend_lazy (it includes web.assets_frontend: a second
  listing would bind twice); the OWL component ships in web.assets_frontend
  like core's portal.signature_form.
"""
import json
import re

from odoo.modules.module import get_manifest
from odoo.tests import tagged
from odoo.tools import file_path

from odoo.addons.bemade_sports_clinic.controllers import app_shell
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

PWA_URLS = ('/my/app.webmanifest', '/my/service-worker.js', '/my/app/offline')


@tagged('post_install', '-at_install')
class TestAppShellPwa1542(AppShellCommon):

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
    def test_manifest_shape(self):
        self._switch(True)
        resp = self.url_open('/my/app.webmanifest', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/manifest+json', resp.headers['Content-Type'])
        manifest = json.loads(resp.text)
        self.assertEqual(manifest['name'], 'Le Fit Crew')
        self.assertEqual(manifest['scope'], '/my/')
        self.assertEqual(manifest['start_url'], '/my/home')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['theme_color'].lower(), '#120e12')
        self.assertEqual(manifest['background_color'].lower(), '#120e12')
        purposes = {(icon['sizes'], icon['purpose']) for icon in manifest['icons']}
        self.assertEqual(purposes, {('192x192', 'any'), ('512x512', 'any'),
                                    ('512x512', 'maskable')})
        for icon in manifest['icons']:
            self.assertEqual(self.url_open(icon['src']).status_code, 200, icon['src'])
        self.assertEqual([s['url'] for s in manifest['shortcuts']], ['/my/home', '/my/players'])

    def test_routes_are_not_multilang(self):
        """Website language redirects must never touch the app URLs (the
        #1433 trap): the routes are declared multilang=False."""
        self._switch(True)
        routing = {}
        for rule in self.env['ir.http'].routing_map().iter_rules():
            routing[rule.rule] = rule.endpoint.routing
        for url in ('/my/app.webmanifest', '/my/service-worker.js', '/my/app/offline',
                    '/my/app/install', '/my/app/save/<string:model>/<int:record_id>'):
            self.assertIn(url, routing)
            self.assertIs(routing[url].get('multilang'), False, url)
        if self.env['ir.module.module']._get('website').state == 'installed':
            fr = self.env['res.lang']._activate_lang('fr_CA')
            for website in self.env['website'].search([]):
                website.language_ids = [(4, fr.id)]
            self.opener.cookies.set('frontend_lang', 'fr_CA')
            for url in PWA_URLS:
                resp = self.url_open(url, allow_redirects=False)
                self.assertEqual(resp.status_code, 200, url)

    # -- UC-P3 -----------------------------------------------------------
    def test_service_worker_never_caches_pages(self):
        self._switch(True)
        resp = self.url_open('/my/service-worker.js', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Service-Worker-Allowed'), '/my/')
        self.assertIn('no-cache', resp.headers.get('Cache-Control', ''))
        self.assertIn('javascript', resp.headers['Content-Type'])
        body = resp.text
        version = get_manifest('bemade_sports_clinic')['version']
        self.assertIn('"sc-app-shell-" + VERSION', body)
        self.assertIn('const VERSION = "%s"' % version, body)
        self.assertNotIn('__SC_SW_', body)
        # No run-time cache write: only the install-time precache.
        self.assertNotIn('.put(', body)
        self.assertEqual(body.count('addAll('), 1)
        # The only /my/ URL in the worker's cache list is the offline page.
        precache = json.loads(re.search(r'const PRECACHE_STATIC = (\[.*?\]);', body).group(1))
        self.assertEqual(precache, list(app_shell.SW_PRECACHE_STATIC))
        self.assertFalse([url for url in precache if url.startswith('/my/')])
        self.assertIn('const OFFLINE_URL = "/my/app/offline"', body)
        for url in precache:
            self.assertEqual(self.url_open(url).status_code, 200, url)
        # Old versions deleted on activate; navigations network-first.
        self.assertIn('caches.delete', body)
        self.assertIn('fetch(request).catch(', body)

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
        self.assertIn('sc_offline.css', text)
        self.assertIn('href="/my/home"', text)

    # -- UC-P5 -----------------------------------------------------------
    def test_install_entry_and_page(self):
        self._switch(True)
        for login in (self._login_coach, self._login_tp):
            login()
            _text, tree = self._get('/my/app/more')
            entry = tree.xpath('//main//a[@data-sc-nav-key="install"]')
            self.assertTrue(entry)
            self.assertEqual(entry[0].get('href'), '/my/app/install')
            text, tree = self._get('/my/app/install')
            self.assertIsNotNone(self._shell(tree))
            for key in ('ios', 'android', 'desktop'):
                self.assertTrue(tree.xpath('//*[@data-sc-install-steps="%s"]' % key), key)
            self.assertTrue(tree.xpath('//*[@data-sc-install-state="installed"][@hidden]'))
            self.assertTrue(tree.xpath('//button[@data-sc-install-prompt]'))
        # Not on the tabs / rail, no banner on the home.
        _text, tree = self._get('/my/home')
        self.assertNotIn('install', self._nav_keys(tree, 'o_sc_tabs'))
        self.assertNotIn('install', self._nav_keys(tree, 'o_sc_rail_nav'))
        self.assertFalse(tree.xpath('//*[@data-sc-install]'))

    def test_manifest_links_in_shell_only(self):
        self._login_tp()
        text, _tree = self._get('/my/home')
        self.assertNotIn('rel="manifest"', text)
        self.assertNotIn('apple-touch-icon', text)
        self._switch(True)
        _text, tree = self._get('/my/home')
        self.assertEqual(tree.xpath('//link[@rel="manifest"]/@href'), ['/my/app.webmanifest'])
        self.assertTrue(tree.xpath('//link[@rel="apple-touch-icon"]'))
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
        for name in ('sc_fetch.js', 'sc_app_ui.js', 'sc_sw_register.js',
                     'sc_autosave_field.js', 'sc_autosave_field.xml'):
            self.assertTrue(any(path.endswith(name) for path in frontend), name)
        # The service worker source is served by its route, never bundled.
        bundled = [p for paths in assets.values() for p in paths if isinstance(p, str)]
        self.assertFalse([p for p in bundled if 'sc_service_worker' in p or p.endswith('/sw/*')])
        self.assertTrue(file_path(app_shell.SW_SOURCE))
