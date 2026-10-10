"""Task 1538 — the app shell behind the system switch. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-S1 (AC1) Switch OFF (prod, the default): ``/my/home`` and ``/my/teams``
  render today's templates — the legacy markers are there, no
  ``data-sc-app-shell`` marker anywhere.
* UC-S2 (AC2/AC4) Switch ON (staging): a coach gets the phone tabs without
  « Clinique », a therapist gets « Clinique »; both get « Réservations » only
  when the bookings card is enabled; the website/portal header and footer are
  NOT rendered; a user without any clinic role keeps the stock portal.
* UC-S3 (AC3) ``sc_nav_mode='crumbs'`` renders the crumb row on a sub-page,
  ``back`` (default) renders the back chevron + context line instead.
* UC-S4 (AC2) The theme attribute follows ``sc_theme`` (dark by default).
* UC-S5 The stock portal home stays reachable from the shell
  (``/my/home?classic=1``).
"""
from unittest.mock import patch

from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.app_shell import AppShellMixin
from odoo.addons.bemade_sports_clinic.tests.portal_cov_common import PortalCovCommon

SWITCH = 'bemade_sports_clinic.app_shell_enabled'


class AppShellCommon(PortalCovCommon):

    def _switch(self, on):
        self.env['ir.config_parameter'].sudo().set_param(SWITCH, 'True' if on else False)

    def _get(self, url):
        resp = self.url_open(url)
        if resp.status_code != 200:
            # Surface the error page's message (a 403 hides its cause).
            tree = lxml_html.fromstring(resp.text or '<p/>')
            detail = ' '.join(' '.join(tree.xpath('//main//text()')).split())[:600]
            self.fail('%s -> %s: %s' % (url, resp.status_code, detail))
        return resp.text, lxml_html.fromstring(resp.text)

    @staticmethod
    def _nav_keys(tree, container_class):
        return tree.xpath(
            "//nav[contains(concat(' ', @class, ' '), ' %s ')]//a/@data-sc-nav-key"
            % container_class)

    @staticmethod
    def _shell(tree):
        nodes = tree.xpath('//*[@data-sc-app-shell]')
        return nodes[0] if nodes else None


@tagged('post_install', '-at_install')
class TestAppShellSwitch1538(AppShellCommon):

    # -- UC-S1 -----------------------------------------------------------
    def test_switch_off_is_the_default_and_keeps_legacy(self):
        self.assertFalse(self.env['ir.config_parameter'].sudo().get_param(SWITCH))
        for login in (self._login_coach, self._login_tp):
            login()
            text, tree = self._get('/my/home')
            self.assertIn('o_portal_my_home', text)
            self.assertIn('portal_sports_category', text)
            self.assertIsNone(self._shell(tree))
            self.assertNotIn('data-sc-app-shell', text)
            text, tree = self._get('/my/teams')
            self.assertIn('o_sc_teams_sort', text)
            self.assertNotIn('data-sc-app-shell', text)

    def test_switch_on_plain_user_keeps_stock_portal(self):
        self._switch(True)
        self._login_plain()
        text, tree = self._get('/my/home')
        self.assertIn('o_portal_my_home', text)
        self.assertIsNone(self._shell(tree))

    # -- UC-S2 -----------------------------------------------------------
    def test_switch_on_coach_tabs_without_clinic(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get('/my/home')
        self.assertIsNotNone(self._shell(tree))
        self.assertNotIn('o_portal_my_home', text)
        self.assertEqual(self._nav_keys(tree, 'o_sc_tabs'),
                         ['teams', 'players', 'activities', 'more'])
        self.assertNotIn('clinic', self._nav_keys(tree, 'o_sc_rail_nav'))
        # The team the coach staffs is listed on the home.
        self.assertIn('PC Team A', text)
        self.assertNotIn('PC Team B', text)

    def test_switch_on_tp_tabs_with_clinic(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/home')
        # Owner review 2026-10-10: « Clinic » left the phone tabs for
        # « More »; the laptop rail keeps it.
        self.assertEqual(self._nav_keys(tree, 'o_sc_tabs'),
                         ['teams', 'players', 'notepad', 'activities', 'more'])
        self.assertIn('clinic', self._nav_keys(tree, 'o_sc_rail_nav'))
        # The therapist-only home section.
        self.assertTrue(tree.xpath('//*[@data-sc-section="home.clinic_teaser"]'))

    def test_coach_home_has_no_clinic_teaser(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertFalse(tree.xpath('//*[@data-sc-section="home.clinic_teaser"]'))
        self.assertTrue(tree.xpath('//*[@data-sc-section="home.team_status"]'))

    def test_bookings_only_when_enabled(self):
        self._switch(True)
        for login in (self._login_coach, self._login_tp):
            login()
            with patch.object(AppShellMixin, '_sc_booking_enabled', return_value=False):
                _text, tree = self._get('/my/home')
                self.assertNotIn('bookings', self._nav_keys(tree, 'o_sc_rail_nav'))
                _text, tree = self._get('/my/app/more')
                self.assertFalse(tree.xpath('//a[@data-sc-nav-key="bookings"]'))
            with patch.object(AppShellMixin, '_sc_booking_enabled', return_value=True):
                _text, tree = self._get('/my/home')
                self.assertIn('bookings', self._nav_keys(tree, 'o_sc_rail_nav'))
                self.assertNotIn('bookings', self._nav_keys(tree, 'o_sc_tabs'))
                _text, tree = self._get('/my/app/more')
                self.assertTrue(tree.xpath('//a[@data-sc-nav-key="bookings"]'))

    def test_no_website_or_portal_header_footer(self):
        # Legacy page carries the frontend header/footer ...
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertTrue(tree.xpath('//header[@id="top"]'))
        # ... the shell does not.
        self._switch(True)
        for url in ('/my/home', '/my/teams', '/my/app/more'):
            _text, tree = self._get(url)
            self.assertIsNotNone(self._shell(tree), url)
            self.assertFalse(tree.xpath('//header[@id="top"]'), url)
            self.assertFalse(tree.xpath('//footer[@id="bottom"]'), url)
            self.assertFalse(tree.xpath('//*[@id="o_main_nav"]'), url)

    def test_teams_page_in_shell(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get('/my/teams')
        self.assertIsNotNone(self._shell(tree))
        self.assertIn('PC Team A', text)
        rows = tree.xpath('//a[contains(@class, "o_sc_entity_row")][@data-sc-team-id]')
        self.assertTrue(rows)
        # Sticky sort (task 1401) survives in the shell.
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_sort")]'))

    # -- UC-S3 -----------------------------------------------------------
    def test_nav_mode_back_is_default(self):
        self._switch(True)
        self._login_coach()
        self.assertEqual(self.coach.sc_nav_mode, 'back')
        _text, tree = self._get('/my/team?team_id=%s' % self.team_a.id)
        self.assertTrue(tree.xpath('//a[contains(@class, "o_sc_back")]'))
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_appbar_context")]'))
        self.assertFalse(tree.xpath('//nav[contains(@class, "o_sc_crumbs")]'))
        self.assertEqual(self._shell(tree).get('data-sc-nav'), 'back')

    def test_nav_mode_crumbs(self):
        self._switch(True)
        self.coach.sc_nav_mode = 'crumbs'
        self._login_coach()
        _text, tree = self._get('/my/team?team_id=%s' % self.team_a.id)
        crumbs = tree.xpath('//nav[contains(@class, "o_sc_crumbs")]')
        self.assertTrue(crumbs)
        self.assertTrue(crumbs[0].xpath('.//a[@href="/my/teams"]'))
        self.assertFalse(tree.xpath('//a[contains(@class, "o_sc_back")]'))
        self.assertEqual(self._shell(tree).get('data-sc-nav'), 'crumbs')

    def test_top_level_page_shows_logo_not_back(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_logo")]'))
        self.assertFalse(tree.xpath('//a[contains(@class, "o_sc_back")]'))

    # -- UC-S4 -----------------------------------------------------------
    def test_theme_attribute_follows_preference(self):
        self._switch(True)
        self._login_tp()
        self.assertEqual(self.tp.sc_theme, 'dark')
        _text, tree = self._get('/my/home')
        self.assertEqual(self._shell(tree).get('data-sc-theme'), 'dark')
        self.tp.sc_theme = 'light'
        _text, tree = self._get('/my/home')
        self.assertEqual(self._shell(tree).get('data-sc-theme'), 'light')

    # -- UC-S5 -----------------------------------------------------------
    def test_classic_home_reachable(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get('/my/home?classic=1')
        self.assertIn('o_portal_my_home', text)
        self.assertIsNone(self._shell(tree))
