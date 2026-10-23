"""Task 1602 — the portal app is forced dark for everyone; the theme toggles
are hidden. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-T1 Parameter ``bemade_sports_clinic.sc_theme_choice_enabled`` absent /
  off (the default): a user whose saved ``sc_theme`` is « light » gets the
  dark shell (``data-sc-theme``, body class, ``theme-color`` meta), and NO
  theme toggle markup — neither the app-bar moon nor the « Plus › Apparence »
  block. The saved preference is kept untouched.
* UC-T2 Parameter on: the same user gets the light shell again and both
  toggles are back.
* UC-T3 ``/my/app/pref`` still accepts ``sc_theme`` (stored), but while the
  choice is off its JSON answer reports the effective theme (dark), so the
  shell script never switches the page to light.

The hidden controls in a real browser stay UNVERIFIED here — the dev-review
click-through covers them.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellTheme1602(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)
        self.tp.sc_theme = 'light'
        self._login_tp()

    def _assert_theme(self, tree, theme):
        self.assertEqual(self._shell(tree).get('data-sc-theme'), theme)
        body_class = tree.xpath('//body/@class')[0].split()
        self.assertIn('o_sc_app_body_%s' % theme, body_class)
        meta = tree.xpath('//meta[@name="theme-color"]/@content')
        self.assertEqual(meta, ['#243925' if theme == 'light' else '#120e12'])

    @staticmethod
    def _toggles(tree):
        return tree.xpath('//*[@name="sc_theme"] | //*[contains(@class, "o_sc_theme_toggle")]'
                          ' | //*[@id="sc_appearance"]')

    # -- UC-T1 -----------------------------------------------------------
    def test_forced_dark_without_parameter(self):
        for url in ('/my/home', '/my/app/more', '/my/app/settings'):
            _text, tree = self._get(url)
            self._assert_theme(tree, 'dark')
            self.assertFalse(self._toggles(tree), url)
        # The saved preference is kept for later.
        self.assertEqual(self.tp.sc_theme, 'light')

    def test_forced_dark_parameter_falsy(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.sc_theme_choice_enabled', '0')
        _text, tree = self._get('/my/app/settings')
        self._assert_theme(tree, 'dark')
        self.assertFalse(self._toggles(tree))

    # -- UC-T2 -----------------------------------------------------------
    def test_choice_enabled_restores_light_and_toggles(self):
        self._theme_choice(True)
        _text, tree = self._get('/my/home')
        self._assert_theme(tree, 'light')
        self.assertTrue(tree.xpath('//form[contains(@class, "o_sc_theme_toggle")]'
                                   '//button[@name="sc_theme"]'))
        _text, tree = self._get('/my/app/settings')  # task 1606: out of « Plus »
        self._assert_theme(tree, 'light')
        self.assertTrue(tree.xpath('//*[@id="sc_appearance"]//button[@name="sc_theme"]'))

    # -- UC-T3 -----------------------------------------------------------
    def test_pref_answer_reports_effective_theme(self):
        self.tp.sc_theme = 'dark'
        resp = self.url_open('/my/app/pref', data={'sc_theme': 'light', 'csrf_token': self._csrf()},
                             headers={'Accept': 'application/json'}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('sc_theme'), 'dark')
        self.tp.invalidate_recordset(['sc_theme'])
        self.assertEqual(self.tp.sc_theme, 'light')
        self._theme_choice(True)
        resp = self.url_open('/my/app/pref', data={'sc_theme': 'light', 'csrf_token': self._csrf()},
                             headers={'Accept': 'application/json'}, allow_redirects=False)
        self.assertEqual(resp.json().get('sc_theme'), 'light')
