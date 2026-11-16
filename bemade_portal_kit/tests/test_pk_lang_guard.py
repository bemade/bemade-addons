# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5389: the profile language guard on multilang pages, next to the
non-multilang fix (``bemade_portal_kit_pwa``'s install page carries the
non-multilang cases: the kit alone has no non-multilang shell page).

Acceptance criteria:

* UC-G1 A multilang shell page (``/my/app/settings``) for a French user on
  an English-default site with a stale English cookie: exactly one 303, to
  the page's French path, then 200 in French; the cookie left on French.
* UC-G2 The same with no cookie and a session whose context still holds
  English (logged in before the profile changed): one 303 to the French
  path, then 200; the cookie the redirect leaves is French (the default
  language queued by the frontend dispatch does not win).
* UC-G3 A user of the default language: 200, no redirect, English.
* UC-G4 A POST is aligned in place (no redirect): ``/my/account`` posted
  with a stale English cookie renders in French.

Synthetic users only. The second language is added to every website when
``website`` is installed; English is made the default (task 5392).
"""
from urllib.parse import urlsplit

from odoo.tests import HttpCase, new_test_user, tagged

from .common import pk_csrf, pk_frontend_langs, pk_kit_shell

ROLES = {'member': {'groups': ('base.group_portal',)}}
SETTINGS = '/my/app/settings'


@tagged('post_install', '-at_install')
class TestPkLangGuard(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Task 5392: an English-default site with French added, whatever the
        # database's site is set to (no skip).
        pk_frontend_langs(cls.env, 'en_US', ('fr_FR',))
        cls.member = new_test_user(cls.env, login='pk_5389_guard', groups='base.group_portal', lang='en_US',
                                   name='PK 5389 Guard')
        cls.member.partner_id.write({'email': 'pk_5389_guard@example.com'})

    def setUp(self):
        super().setUp()
        shell = pk_kit_shell(self.env, roles=ROLES)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)

    def _login(self, lang):
        self.member.lang = lang
        self.env.flush_all()
        self.authenticate('pk_5389_guard', 'pk_5389_guard')

    def _cookie(self):
        values = [c.value for c in self.opener.cookies if c.name == 'frontend_lang']
        self.assertLessEqual(len(values), 1, values)
        return values[0] if values else None

    def _set_cookie(self, value):
        for cookie in [c for c in self.opener.cookies if c.name == 'frontend_lang']:
            self.opener.cookies.clear(cookie.domain, cookie.path, cookie.name)
        if value:
            self.opener.cookies.set('frontend_lang', value, domain=urlsplit(self.base_url()).hostname, path='/')

    def _assert_one_redirect_to_french(self):
        response = self.url_open(SETTINGS, allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        location = urlsplit(response.headers['Location']).path
        self.assertTrue(location.endswith(SETTINGS), location)
        self.assertNotEqual(location, SETTINGS, 'a multilang page: its French path')
        self.assertEqual(self._cookie(), 'fr_FR')
        response = self.url_open(location, allow_redirects=False)
        self.assertEqual(response.status_code, 200, 'served at once (one redirect in all)')
        self.assertIn('lang="fr-FR"', response.text)

    # ------------------------------------------------------------- UC-G1
    def test_multilang_stale_cookie(self):
        self._login('fr_FR')
        self._set_cookie('en_US')
        self._assert_one_redirect_to_french()

    # ------------------------------------------------------------- UC-G2
    def test_multilang_english_session_no_cookie(self):
        self._login('en_US')
        self.member.lang = 'fr_FR'
        self.env.flush_all()
        self._set_cookie(None)
        self._assert_one_redirect_to_french()

    # ------------------------------------------------------------- UC-G3
    def test_default_language_user(self):
        self._login('en_US')
        self._set_cookie('en_US')
        response = self.url_open(SETTINGS, allow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn('lang="en-US"', response.text)
        self.assertEqual(self._cookie(), 'en_US')

    # ------------------------------------------------------------- UC-G4
    def test_post_aligned_in_place(self):
        self._login('fr_FR')
        csrf = pk_csrf(self, '/my/account')
        self._set_cookie('en_US')
        response = self.url_open('/my/account', data={'csrf_token': csrf, 'name': ''}, allow_redirects=False)
        self.assertEqual(response.status_code, 200, 'no redirect for a POST')
        self.assertIn('lang="fr-FR"', response.text)
        self.assertEqual(self._cookie(), 'fr_FR')
