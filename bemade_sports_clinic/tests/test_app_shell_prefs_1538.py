"""Task 1538 — per-user navigation / theme preferences and the « Plus » page.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-P1 ``sc_nav_mode`` (back | crumbs, default back) and ``sc_theme``
  (dark | light, default dark) are self-readable and self-writable by a
  portal user, and by nobody else's hand.
* UC-P2 ``POST /my/app/pref`` (CSRF) sets ONLY those two fields on the
  CALLER's own record: another field → 400, a bad value → 400, another user's
  record → 403, nothing written in either case. A JSON caller gets JSON; a
  plain form post is redirected back (no-JS path).
* UC-P3 (AC4) « Plus » (``/my/app/more``) lists the role-scoped app entries
  and the stock portal links (account, security, the classic portal home
  with every other app's documents, logout) so nothing becomes unreachable.
"""
from lxml import html as lxml_html

from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellPrefs1538(AppShellCommon):

    def _post_pref(self, data, json_accept=True):
        data = dict(data)
        data.setdefault('csrf_token', self._csrf())
        headers = {'Accept': 'application/json'} if json_accept else {}
        return self.url_open('/my/app/pref', data=data, headers=headers,
                             allow_redirects=False)

    # -- UC-P1 -----------------------------------------------------------
    def test_prefs_self_writable_and_defaults(self):
        self.assertEqual(self.coach.sc_nav_mode, 'back')
        self.assertEqual(self.coach.sc_theme, 'dark')
        self.coach.with_user(self.coach).write({'sc_nav_mode': 'crumbs', 'sc_theme': 'light'})
        self.assertEqual(self.coach.sc_nav_mode, 'crumbs')
        self.assertEqual(self.coach.sc_theme, 'light')
        with self.assertRaises(AccessError):
            self.tp.with_user(self.coach).write({'sc_theme': 'light'})

    # -- UC-P2 -----------------------------------------------------------
    def test_pref_route_sets_own_prefs_json(self):
        self._login_coach()
        resp = self._post_pref({'sc_theme': 'light'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('sc_theme'), 'light')
        self.assertEqual(self.coach.sc_theme, 'light')
        resp = self._post_pref({'sc_nav_mode': 'crumbs'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.coach.sc_nav_mode, 'crumbs')

    def test_pref_route_form_post_redirects_back(self):
        self._login_coach()
        resp = self._post_pref({'sc_theme': 'light', 'redirect': '/my/teams'},
                               json_accept=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].endswith('/my/teams'))
        self.assertEqual(self.coach.sc_theme, 'light')
        # An off-site redirect is ignored.
        resp = self._post_pref({'sc_theme': 'dark', 'redirect': '//evil.example.com/x'},
                               json_accept=False)
        self.assertNotIn('evil.example.com', resp.headers['Location'])

    def test_pref_route_rejects_other_fields(self):
        self._login_coach()
        before = self.coach.name
        resp = self._post_pref({'sc_theme': 'light', 'name': 'Renamed'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.coach.name, before)
        self.assertEqual(self.coach.sc_theme, 'dark')
        resp = self._post_pref({'teams_sort_mode': 'alpha'})
        self.assertEqual(resp.status_code, 400)

    def test_pref_route_rejects_bad_values(self):
        self._login_coach()
        resp = self._post_pref({'sc_theme': 'neon'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.coach.sc_theme, 'dark')
        resp = self._post_pref({})
        self.assertEqual(resp.status_code, 400)

    def test_pref_route_rejects_other_users_record(self):
        self._login_coach()
        resp = self._post_pref({'sc_theme': 'light', 'user_id': str(self.tp.id)})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.tp.sc_theme, 'dark')
        self.assertEqual(self.coach.sc_theme, 'dark')

    def test_pref_route_requires_csrf(self):
        self._login_coach()
        resp = self.url_open('/my/app/pref', data={'sc_theme': 'light', 'csrf_token': 'bogus'},
                             allow_redirects=False)
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertEqual(self.coach.sc_theme, 'dark')

    # -- UC-P3 -----------------------------------------------------------
    def _more(self):
        resp = self.url_open('/my/app/more')
        self.assertEqual(resp.status_code, 200)
        return lxml_html.fromstring(resp.text)

    def test_more_lists_stock_portal_links(self):
        self._switch(True)
        for login in (self._login_coach, self._login_tp):
            login()
            tree = self._more()
            hrefs = set(tree.xpath('//main//a/@href'))
            for href in ('/my/account', '/my/security', '/my/home?classic=1',
                         '/my/events'):
                self.assertIn(href, hrefs)
            self.assertTrue([h for h in hrefs if h.startswith('/web/session/logout')])
            # Appearance + navigation preference controls.
            self.assertTrue(tree.xpath('//form[@data-sc-pref]//*[@name="sc_theme"]'))
            self.assertTrue(tree.xpath('//form[@data-sc-pref]//*[@name="sc_nav_mode"]'))

    def test_more_role_scoped_entries(self):
        self._switch(True)
        self._login_coach()
        keys = self._more().xpath('//main//a/@data-sc-nav-key')
        self.assertNotIn('notepad', keys)
        self.assertNotIn('timesheets', keys)
        self._login_tp()
        keys = self._more().xpath('//main//a/@data-sc-nav-key')
        self.assertIn('notepad', keys)
        self.assertIn('timesheets', keys)

    def test_more_with_switch_off_falls_back_home(self):
        """Switch off: the app page does not exist for users (prod)."""
        self._login_tp()
        resp = self.url_open('/my/app/more', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].endswith('/my/home'))
