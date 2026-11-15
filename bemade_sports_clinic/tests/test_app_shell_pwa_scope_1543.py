"""Task 1543 — the installable app covers the WHOLE origin (scope ``/``).

Root cause: a session in a non-default website language is served under
``/<lang>/my/...`` (e.g. ``/en/my/team``), outside the P1b ``/my/`` scope, so
the service worker never saw the navigation and an offline reload showed the
browser's own error. Owner decision 2026-09-28: widen the worker and the
manifest to ``/`` instead of making every portal route ``multilang=False``.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-S1 (AC1) ``/my/service-worker.js`` is served with
  ``Service-Worker-Allowed: /``; the manifest's ``scope`` is ``/``
  (``start_url`` still ``/my/home``, ``id`` unchanged so installs keep their
  identity).
* UC-S2 / UC-S3 (the page script's scope and kill switch): task 5201 (kit
  P6), bemade_portal_kit_pwa's (tests/test_pk_pwa_static.py and its
  kill-switch tour).
* UC-S4 (AC1/AC2) Website-aware: with a second website language active and
  the ``frontend_lang`` cookie set to it, the manifest, the worker and the
  offline page answer 200 WITHOUT a language redirect, while a shell page is
  served under the language prefix — the reason the scope must be ``/``.
  No-op when ``website`` is not installed (``odoo-dev test``); meaningful on
  the addon CI, which installs it.
* UC-S5 (AC1) The worker still never writes a page or JSON to a cache and
  answers any in-scope navigation (prefixed or not) network-first with the
  precached offline page as the offline fallback.
"""
import json
import re

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

PWA_URLS = ('/my/app.webmanifest', '/my/service-worker.js', '/my/app/offline')


@tagged('post_install', '-at_install')
class TestAppShellPwaScope1543(AppShellCommon):

    # -- UC-S1 -----------------------------------------------------------
    def test_worker_allowed_whole_origin(self):
        self._switch(True)
        resp = self.url_open('/my/service-worker.js', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Service-Worker-Allowed'), '/')

    def test_manifest_scope_whole_origin(self):
        self._switch(True)
        resp = self.url_open('/my/app.webmanifest', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        manifest = json.loads(resp.text)
        self.assertEqual(manifest['scope'], '/')
        self.assertEqual(manifest['start_url'], '/my/home')
        self.assertEqual(manifest['id'], '/my/home')
        self.assertEqual(manifest['display'], 'standalone')

    # -- UC-S4 -----------------------------------------------------------
    def test_prefixed_language_session(self):
        """No-op without ``website`` (no multilang routing exists then)."""
        if self.env['ir.module.module']._get('website').state != 'installed':
            return
        self._switch(True)
        websites = self.env['website'].search([])
        default = websites[:1].default_lang_id
        code = 'fr_CA' if default.code != 'fr_CA' else 'en_US'
        lang = self.env['res.lang']._activate_lang(code)
        for website in websites:
            website.language_ids = [(4, lang.id)]
        self._login_tp()
        self.opener.cookies.set('frontend_lang', code)
        # The app's own files: never redirected to a language prefix.
        for url in PWA_URLS:
            resp = self.url_open(url, allow_redirects=False)
            self.assertEqual(resp.status_code, 200, url)
        # A shell page IS redirected under the prefix: outside a /my/ scope.
        resp = self.url_open('/my/home', allow_redirects=False)
        self.assertIn(resp.status_code, (301, 302, 303), resp.status_code)
        location = resp.headers['Location']
        prefix = '/%s/my/home' % lang.url_code
        self.assertTrue(location.endswith(prefix) or (prefix + '?') in location, location)
        _text, tree = self._get(prefix)
        self.assertIsNotNone(self._shell(tree))
        # ... and the worker scope covers it.
        resp = self.url_open('/my/service-worker.js', allow_redirects=False)
        allowed = resp.headers.get('Service-Worker-Allowed')
        self.assertTrue(prefix.startswith(allowed), (prefix, allowed))

    # -- UC-S5 -----------------------------------------------------------
    def test_worker_still_never_caches_pages(self):
        self._switch(True)
        body = self.url_open('/my/service-worker.js', allow_redirects=False).text
        self.assertNotIn('.put(', body)
        self.assertEqual(body.count('addAll('), 1)
        self.assertIn('const OFFLINE_URL = "/my/app/offline"', body)
        self.assertIn('request.mode === "navigate"', body)
        self.assertIn('fetch(request).catch(', body)
        # No path filter on navigations: /en/my/... is handled like /my/...
        navigate = re.search(r'request\.mode === "navigate"\) \{(.*?)return;', body, re.S)
        self.assertTrue(navigate)
        self.assertNotIn('pathname', navigate.group(1))
