"""Task 1795, review round 2 (2026-11-27) — « Se déconnecter » stays in the
app: it ends on the login page, not the public website home (``/``).
Synthetic fixtures only.

Before: the client's « Plus › Se déconnecter » and the kit's user menu (staff
and client alike, the same mechanism) used ``/web/session/logout?redirect=/``.

Acceptance criteria covered here:

* UC-L1 A client's « Plus » and user menu sign out with
  ``redirect=/web/login``; so do a therapist's and a coach's user menu.
* UC-L2 Following the link ends on ``/web/login`` (200), logged out.
* UC-L3 « Pas d'accès »'s « Se déconnecter » ends on the login page too.
"""
from urllib.parse import urlsplit

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

LOGOUT_TO_LOGIN = '/web/session/logout?redirect=/web/login'


@tagged('post_install', '-at_install')
class TestAppLogout1795(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _logout_links(self, tree):
        return tree.xpath('//a[starts-with(@href, "/web/session/logout")]/@href')

    # -- UC-L1 -----------------------------------------------------------
    def test_client_logout_links(self):
        self._login_plain()
        _text, tree = self._get('/my/app/more')
        self.assertEqual(tree.xpath('//a[@data-pk-nav-key="logout"]/@href'), [LOGOUT_TO_LOGIN])
        menu = tree.xpath('//*[@data-pk-user-menu-popup]')[0]
        self.assertTrue(self._logout_links(menu))
        self.assertEqual(set(self._logout_links(menu)), {LOGOUT_TO_LOGIN})
        self.assertEqual(set(self._logout_links(tree)), {LOGOUT_TO_LOGIN})

    def test_staff_logout_links(self):
        for login in (self._login_tp, self._login_coach):
            login()
            for url in ('/my/home', '/my/teams'):
                _text, tree = self._get(url)
                menu = tree.xpath('//*[@data-pk-user-menu-popup]')[0]
                self.assertEqual(self._logout_links(menu), [LOGOUT_TO_LOGIN], (login.__name__, url))

    # -- UC-L2 -----------------------------------------------------------
    def test_logout_lands_on_login(self):
        self._login_plain()
        resp = self.url_open(LOGOUT_TO_LOGIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(urlsplit(resp.url).path, '/web/login')
        # Logged out: an app page sends to the login again.
        resp = self.url_open('/my/home', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/web/login', resp.headers['Location'])

    # -- UC-L3 -----------------------------------------------------------
    def test_no_access_logout(self):
        self._login_plain()
        resp = self.url_open('/my/teams')
        self.assertEqual(resp.status_code, 403)
        self.assertIn('href="%s"' % LOGOUT_TO_LOGIN, resp.text)
        self.assertNotIn('logout?redirect=/"', resp.text)
