# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5392: ``/my`` reaches the viewer's app home with the kit alone.

Acceptance criteria:

* UC-H1 ``portal.kit._pk_home_url()``: for a user in an app (switch on, an
  app role), the app's home: its brand's ``home_url`` (``_pk_apps()[app]
  ['brand']``); False (the portal home) when that is ``/my`` or
  ``/my/home`` (the kit's neutral brand), not a same-site path, for a user
  without an app role, or with the switch off.
* UC-H2 ``GET /my`` and ``GET /my/home`` redirect (303) such a user to the
  app's home; ``?classic=1``, a user without an app role, an app without a
  home of its own and the switch off get the portal home (200). A user
  served in a non-default language keeps its URL prefix. With
  ``bemade_portal_kit_dashboard`` installed, ``/my/home`` is the
  dashboard's (its own tests): UC-H2 is skipped there.
Synthetic users and apps only.
"""
from urllib.parse import urlsplit

from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from .common import pk_frontend_langs, pk_hooks, pk_kit_shell

ROLES = {'pk_h_member': {'groups': ('base.group_portal',), 'app': 'pk_h_app'}}
HOME = '/my/app/more'


def _apps(home_url=HOME):
    return {'pk_h_app': {'brand': {'home_url': home_url}}}


class HomeCommon:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env, 'en_US', ('fr_FR',))
        cls.member = new_test_user(cls.env, login='pk_h_member', groups='base.group_portal', lang='en_US')
        cls.staff = new_test_user(cls.env, login='pk_h_staff', groups='base.group_user')

    def setUp(self):
        super().setUp()
        shell = pk_kit_shell(self.env, roles=ROLES)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)
        self.params = self.env['ir.config_parameter'].sudo()

    def _with_apps(self, home_url=HOME):
        return pk_hooks(self.env, _pk_apps=lambda _orig: _apps(home_url))


@tagged('post_install', '-at_install')
class TestPkHomeUrl(HomeCommon, TransactionCase):

    def _url(self, user):
        return self.env['portal.kit'].with_user(user)._pk_home_url()

    def test_app_home(self):
        with self._with_apps():
            self.assertEqual(self._url(self.member), HOME)
            self.assertFalse(self._url(self.staff), 'no app role')
            self.params.set_param('bemade_portal_kit.enabled', 'False')
            self.assertFalse(self._url(self.member), 'switch off')

    def test_no_home_of_its_own(self):
        for url in ('/my', '/my/home', '/my/', 'https://evil.example/x', '//evil.example', None):
            with self.subTest(url=url), self._with_apps(url):
                self.assertFalse(self._url(self.member))
        # The kit's neutral brand (no app registered): the portal home.
        self.assertFalse(self._url(self.member))


@tagged('post_install', '-at_install')
class TestPkHomeHttp(HomeCommon, HttpCase):

    def setUp(self):
        super().setUp()
        if self.env['ir.module.module']._get('bemade_portal_kit_dashboard').state == 'installed':
            self.skipTest("the dashboard's home is /my/home's (its own tests)")

    def _get(self, url, login='pk_h_member'):
        self.authenticate(login, login)
        return self.url_open(url, allow_redirects=False)

    def test_redirects_to_the_app_home(self):
        with self._with_apps():
            for url in ('/my', '/my/home'):
                response = self._get(url)
                self.assertEqual(response.status_code, 303, url)
                self.assertEqual(urlsplit(response.headers['Location']).path, HOME, url)
            self.assertEqual(self._get('/my/home?classic=1').status_code, 200, 'classic')
            self.assertEqual(self._get('/my/home', login='pk_h_staff').status_code, 200, 'no app role')
            # Landed: the app's home itself answers.
            self.authenticate('pk_h_member', 'pk_h_member')
            self.assertEqual(self.url_open('/my').status_code, 200)

    def test_portal_home_otherwise(self):
        with self._with_apps('/my'):
            self.assertEqual(self._get('/my').status_code, 200, 'no home of its own')
        self.assertEqual(self._get('/my').status_code, 200, 'no app registered')
        with self._with_apps():
            self.params.set_param('bemade_portal_kit.enabled', 'False')
            self.assertEqual(self._get('/my').status_code, 200, 'switch off')

    def test_language_prefix_kept(self):
        self.member.lang = 'fr_FR'
        self.env.flush_all()
        code = self.env['res.lang']._get_data(code='fr_FR').url_code
        with self._with_apps():
            response = self._get('/%s/my' % code)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(urlsplit(response.headers['Location']).path, '/%s%s' % (code, HOME))
