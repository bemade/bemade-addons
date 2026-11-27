"""Task 1541 review (2026-11-26) — « Pas d'accès » follows the theme.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-T1 By default (theme choice off, or a user who never picked another
  theme) the page follows the device: it is marked ``data-sc-theme-auto``
  (dark, light under ``prefers-color-scheme: light`` in the stylesheet, no
  script) with a browser bar colour per device scheme.
* UC-T2 The theme choice on and the user's own pick of the light theme: the
  page renders light (root, body class, browser bar colour), no device
  script.
* UC-T3 The page stays a 403 with no app navigation.
"""
from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestNoAccessTheme1541(AppShellCommon):

    def _page(self):
        resp = self.url_open('/my/teams', allow_redirects=False)
        self.assertEqual(resp.status_code, 403)
        tree = lxml_html.fromstring(resp.text)
        root = tree.xpath('//*[@data-sc-no-access-page]')
        self.assertTrue(root)
        self.assertFalse(tree.xpath('//*[@data-pk-app-shell]'))
        return resp.text, tree, root[0]

    def test_follows_the_device_by_default(self):
        for choice in (False, True):
            with self.subTest(choice=choice):
                self._theme_choice(choice)
                self._login_plain()
                text, tree, root = self._page()
                self.assertEqual(root.get('data-sc-theme-auto'), '1')
                self.assertIn('o_sc_no_access_auto', tree.xpath('//body/@class')[0])
                self.assertEqual(
                    sorted(tree.xpath('//meta[@name="theme-color"]/@media')),
                    ['(prefers-color-scheme: dark)', '(prefers-color-scheme: light)'])
                self.assertNotIn('<script>(function', text)

    def test_user_light_pick_with_choice_on(self):
        self._theme_choice(True)
        self.plain.pk_theme = 'light'
        self._login_plain()
        text, tree, root = self._page()
        self.assertEqual(root.get('data-pk-theme'), 'light')
        self.assertIsNone(root.get('data-sc-theme-auto'))
        self.assertNotIn('o_sc_no_access_auto', tree.xpath('//body/@class')[0])
        self.assertIn('o_pk_app_body_light', tree.xpath('//body/@class')[0])
        self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#243925'])

    def test_user_light_pick_ignored_with_choice_off(self):
        self._theme_choice(False)
        self.plain.pk_theme = 'light'
        self._login_plain()
        _text, _tree, root = self._page()
        self.assertEqual(root.get('data-sc-theme-auto'), '1')
