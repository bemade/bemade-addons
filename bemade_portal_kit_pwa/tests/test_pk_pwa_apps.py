# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5391: the installable app per app — two synthetic apps (« north »,
« south ») in one database.

Acceptance criteria:

* UC-WA1 The public ``/my/app.webmanifest`` is the database's default app
  (the system parameter, else the first app); ``/my/app/<app>.webmanifest``
  is that app's (its start URL, id and shortcuts from its ``pwa``
  registration); an unknown app answers 404, as every manifest with the
  switch off.
* UC-WA2 With a single app, ``/my/app.webmanifest`` carries that app's id,
  start URL and shortcuts, exactly as the hooks gave them before task 5391
  (an installed app keeps its URL and id).
* UC-WA3 A shell page links its viewer's app's manifest: the default app
  ``/my/app.webmanifest``, any other app its own.
* UC-WA4 The offline page takes the default app's offline style.
Synthetic users and apps only.
"""
import json

from lxml import html as lxml_html

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_extra_roles, pk_hooks

from .common import pk_pwa_shell

ROLES = {
    'n_member': {'groups': (), 'app': 'north'},
    's_member': {'groups': (), 'app': 'south'},
}
HOLDERS = {'pk_wa_north': {'n_member'}, 'pk_wa_south': {'s_member'}}
APPS = {
    'north': {'sequence': 20, 'pwa': {
        'start_url': '/my/north', 'manifest_id': '/my/north-app',
        'shortcuts': lambda kit: [{'name': 'North One', 'url': '/my/n1'}],
        'offline_style': {'accent': '#aa0000'}}},
    'south': {'sequence': 10, 'pwa': {
        'start_url': '/my/south', 'shortcuts': [{'name': 'South One', 'url': '/my/s1'}],
        'offline_style': lambda kit, pwa: {'accent': '#00aa00'}}},
}


@tagged('post_install', '-at_install')
class TestPkPwaApps(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for login in HOLDERS:
            new_test_user(cls.env, login=login, groups='base.group_portal', lang='en_US')

    def setUp(self):
        super().setUp()
        for ctx in (pk_pwa_shell(self.env, roles=ROLES),
                    pk_hooks(self.env, _pk_apps=lambda _orig: APPS),
                    pk_extra_roles(self.env, lambda user: frozenset(HOLDERS.get(user.login, ())))):
            ctx.__enter__()
            self.addCleanup(ctx.__exit__, None, None, None)
        self.params = self.env['ir.config_parameter'].sudo()
        self.params.set_param('bemade_portal_kit.default_app', False)

    def _manifest(self, url, status=200):
        resp = self.url_open(url, allow_redirects=False)
        self.assertEqual(resp.status_code, status, url)
        if status == 200:
            self.assertIn('application/manifest+json', resp.headers['Content-Type'])
            return json.loads(resp.text)
        return None

    # ------------------------------------------------------------ UC-WA1
    def test_default_and_per_app_manifests(self):
        # south: the first app (sequence 10).
        manifest = self._manifest('/my/app.webmanifest')
        self.assertEqual((manifest['id'], manifest['start_url']), ('/my/south', '/my/south'))
        self.assertEqual(manifest['shortcuts'], [{'name': 'South One', 'url': '/my/s1'}])
        manifest = self._manifest('/my/app/north.webmanifest')
        self.assertEqual((manifest['id'], manifest['start_url']), ('/my/north-app', '/my/north'))
        self.assertEqual(manifest['shortcuts'], [{'name': 'North One', 'url': '/my/n1'}])
        self.assertEqual(self._manifest('/my/app/south.webmanifest')['start_url'], '/my/south')
        self._manifest('/my/app/nowhere.webmanifest', status=404)
        # The system parameter names the default app.
        self.params.set_param('bemade_portal_kit.default_app', 'north')
        self.assertEqual(self._manifest('/my/app.webmanifest')['start_url'], '/my/north')
        self.params.set_param('bemade_portal_kit.enabled', False)
        self._manifest('/my/app/north.webmanifest', status=404)
        self._manifest('/my/app.webmanifest', status=404)

    # ------------------------------------------------------------ UC-WA2
    def test_single_app_manifest_unchanged(self):
        with pk_hooks(self.env, _pk_roles=lambda _orig: {'n_member': ROLES['n_member']},
                      _pk_apps=lambda _orig: {'north': APPS['north']}):
            manifest = self._manifest('/my/app.webmanifest')
            self.assertEqual((manifest['id'], manifest['start_url']), ('/my/north-app', '/my/north'))
            self.assertEqual(manifest['shortcuts'], [{'name': 'North One', 'url': '/my/n1'}])
            self.assertEqual(manifest, self._manifest('/my/app/north.webmanifest'))

    # ------------------------------------------------------------ UC-WA3
    def test_shell_page_links_the_viewers_manifest(self):
        for login, href in (('pk_wa_south', '/my/app.webmanifest'), ('pk_wa_north', '/my/app/north.webmanifest')):
            self.authenticate(login, login)
            resp = self.url_open('/my/app/more')
            self.assertEqual(resp.status_code, 200, login)
            tree = lxml_html.document_fromstring(resp.text)
            self.assertEqual(tree.xpath('//head/link[@rel="manifest"]/@href'), [href], login)

    # ------------------------------------------------------------ UC-WA4
    def test_offline_page_is_the_default_apps(self):
        self.assertIn('--pk-offline-accent: #00aa00', self.url_open('/my/app/offline').text)
        self.params.set_param('bemade_portal_kit.default_app', 'north')
        self.assertIn('--pk-offline-accent: #aa0000', self.url_open('/my/app/offline').text)
