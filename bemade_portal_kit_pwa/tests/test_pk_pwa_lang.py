# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5389: « Install the app » for a user whose profile language is not
the website's default language.

Acceptance criteria:

* UC-L1 ``/my/app/install`` (a non-multilang page) for a French user on an
  English-default site, without a ``frontend_lang`` cookie and with a stale
  English one: 200 at once (no redirect, so no loop), rendered in French,
  the ``frontend_lang`` cookie left on French.
* UC-L1b A session whose context still holds the default language (logged
  in before the profile changed) and no cookie: 200 at once, French, the
  ``frontend_lang`` cookie the response leaves is French (the default
  language queued by the frontend dispatch does not win).
* UC-L2 The same page for a user of the default language: 200, no
  redirect, English, the cookie not changed to another language.

Synthetic users only. The second language is added to every website when
``website`` is installed; English is made the default (task 5392).
"""
from urllib.parse import urlsplit

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit.tests.common import pk_frontend_langs

from .common import pk_pwa_shell

ROLES = {'member': {'groups': ('base.group_portal',)}}
INSTALL = '/my/app/install'


@tagged('post_install', '-at_install')
class TestPkPwaLang(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Task 5392: an English-default site with French added, whatever the
        # database's site is set to (no skip).
        pk_frontend_langs(cls.env, 'en_US', ('fr_FR',))
        cls.member = new_test_user(cls.env, login='pk_5389_member', groups='base.group_portal', lang='en_US',
                                   name='PK 5389 Member')
        cls.member.partner_id.email = 'pk_5389_member@example.com'

    def setUp(self):
        super().setUp()
        shell = pk_pwa_shell(self.env, roles=ROLES)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)

    def _login(self, lang):
        self.member.lang = lang
        self.env.flush_all()
        self.authenticate('pk_5389_member', 'pk_5389_member')

    def _cookie(self):
        """The client's ``frontend_lang`` (None when unset)."""
        values = [c.value for c in self.opener.cookies if c.name == 'frontend_lang']
        self.assertLessEqual(len(values), 1, values)
        return values[0] if values else None

    def _set_cookie(self, value):
        """Replace the client's ``frontend_lang`` (None: remove it)."""
        for cookie in [c for c in self.opener.cookies if c.name == 'frontend_lang']:
            self.opener.cookies.clear(cookie.domain, cookie.path, cookie.name)
        if value:
            self.opener.cookies.set('frontend_lang', value, domain=urlsplit(self.base_url()).hostname, path='/')

    def _assert_served(self, response, html_lang):
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.history, 'served without any redirect')
        self.assertTrue(response.url.split('?')[0].endswith(INSTALL), response.url)
        self.assertIn('lang="%s"' % html_lang, response.text)
        self.assertIn('data-pk-install', response.text)

    # ------------------------------------------------------------- UC-L1
    def test_french_user_no_cookie(self):
        self._login('fr_FR')
        self._set_cookie(None)
        self._assert_served(self.url_open(INSTALL), 'fr-FR')
        self.assertIn(self._cookie(), (None, 'fr_FR'))

    def test_french_user_stale_english_cookie(self):
        self._login('fr_FR')
        self._set_cookie('en_US')
        response = self.url_open(INSTALL, allow_redirects=False)
        self.assertEqual(response.status_code, 200, 'no redirect to itself')
        self.assertEqual(self._cookie(), 'fr_FR', 'the cookie follows the profile')
        # A client that keeps no cookie (each visit with the stale one):
        # still served, never a redirect to the same URL.
        self._set_cookie('en_US')
        self._assert_served(self.url_open(INSTALL), 'fr-FR')
        # The next visit, with the cookie the page left.
        self._assert_served(self.url_open(INSTALL), 'fr-FR')

    # ------------------------------------------------------------ UC-L1b
    def test_french_profile_english_session(self):
        self._login('en_US')
        self.member.lang = 'fr_FR'
        self.env.flush_all()
        self._set_cookie(None)
        response = self.url_open(INSTALL, allow_redirects=False)
        self.assertEqual(response.status_code, 200, 'no redirect to itself')
        self.assertIn('lang="fr-FR"', response.text)
        cookies = [c for c in response.raw.headers.getlist('Set-Cookie') if c.startswith('frontend_lang=')]
        self.assertTrue(cookies)
        self.assertTrue(cookies[-1].startswith('frontend_lang=fr_FR;'), cookies)
        self.assertEqual(self._cookie(), 'fr_FR')

    # ------------------------------------------------------------- UC-L2
    def test_default_language_user(self):
        self._login('en_US')
        self._set_cookie('en_US')
        self._assert_served(self.url_open(INSTALL), 'en-US')
        self.assertEqual(self._cookie(), 'en_US')
