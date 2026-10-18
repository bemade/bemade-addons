"""Task 1622 — the activities page opened from the app-bar clock has a way
back (owner 2026-10-18). Synthetic fixtures only (this repository is public).

``/my/activities`` is a top-level page (logo, no back). Opened from the app
bar clock (#1592) it shows the back arrow (phone AND laptop) to the page the
user was on: ``sc_app_nav.js`` turns it into ``history.back()`` when the
previous entry of the tab is an in-app page; otherwise its href is the page
the clock link was clicked on, passed along as ``sc_from``.

Acceptance criteria:

* UC-C1 The clock link carries its origin: on every shell page its href is
  ``/my/activities?sc_clock=1&sc_from=<current path + query>`` (the flash
  args ``success`` / ``error`` dropped). On the activities page itself it
  keeps the origin it was opened with (never itself); without one it is the
  plain ``/my/activities?sc_clock=1``.
* UC-C2 Opened from the clock with a readable in-app origin, the activities
  page renders the back arrow (href = the origin, its query kept) and the
  trail of the origin page; without ``sc_from`` it stays top level (logo).
* UC-C3 The arrow stays when switching tabs (Overdue / All / …): the tab
  links keep ``sc_from`` (and still drop the clock marker).
* UC-C4 No open redirect: an external host, ``//host``, ``javascript:``, a
  backslash or control character is ignored (no arrow, not passed on by the
  clock link). A same-site path that is not a registered app page, or a
  record the user cannot read, never becomes the href: the arrow goes to the
  home (history.back() still returns to the real previous page in-app).
* UC-C5 The record-scoped activities wrappers (/my/team/activities …) keep
  their declared parent.
"""
from urllib.parse import quote

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_nav_1579 import HOME, Nav1579Common

CLOCK = '/my/activities?sc_clock=1'


def _q(url):
    return quote(url, safe='')


class Clock1622Common(Nav1579Common):

    def setUp(self):
        super().setUp()
        self.player_url = '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)

    def _clock_href(self, url):
        _text, tree = self._get(url)
        bar = tree.xpath('//header[contains(@class, "o_sc_appbar")]//a[@data-sc-activity-clock-bar]')
        self.assertEqual(len(bar), 1, url)
        return bar[0].get('href')


@tagged('post_install', '-at_install')
class TestClockBack1622(Clock1622Common):

    # -- UC-C1 -----------------------------------------------------------
    def test_clock_link_carries_the_origin(self):
        self.assertEqual(self._clock_href(HOME), CLOCK + '&sc_from=' + _q(HOME))
        self.assertEqual(self._clock_href(self.player_url),
                         CLOCK + '&sc_from=' + _q(self.player_url))
        self.assertEqual(self._clock_href(self.players_tab),
                         CLOCK + '&sc_from=' + _q(self.players_tab))

    def test_clock_link_drops_flash_args(self):
        href = self._clock_href(self.player_url + '&success=saved&error=x')
        self.assertEqual(href, CLOCK + '&sc_from=' + _q(self.player_url))

    def test_clock_link_on_the_activities_page(self):
        self.assertEqual(self._clock_href('/my/activities'), CLOCK)
        self.assertEqual(self._clock_href(CLOCK), CLOCK)
        self.assertEqual(self._clock_href(CLOCK + '&sc_from=' + _q(self.player_url)),
                         CLOCK + '&sc_from=' + _q(self.player_url))

    # -- UC-C2 -----------------------------------------------------------
    def test_arrow_back_to_the_origin(self):
        back, crumbs, current, _context = self._nav(CLOCK + '&sc_from=' + _q(self.player_url))
        self.assertEqual(back, [self.player_url])
        self.assertEqual(crumbs[-1], (self.player_url, self.player_name))
        self.assertEqual(crumbs[:2], [('/my/teams', 'Teams'), (self.players_tab, 'PC Team A')])
        self.assertEqual(current, 'Activities')
        back, crumbs, _current, _context = self._nav(CLOCK + '&sc_from=' + _q(HOME))
        self.assertEqual(back, [HOME])
        self.assertEqual(crumbs, [(HOME, 'Home')])

    def test_without_origin_stays_top_level(self):
        for url in ('/my/activities', CLOCK):
            _text, tree = self._get(url)
            self.assertTrue(tree.xpath('//a[contains(@class, "o_sc_logo")]'), url)
            back, crumbs, _current, _context = self._nav(url)
            self.assertEqual((back, crumbs), ([], []), url)

    # -- UC-C3 -----------------------------------------------------------
    def test_arrow_kept_across_tabs(self):
        _text, tree = self._get(CLOCK + '&sc_from=' + _q(self.player_url))
        hrefs = tree.xpath('//a[@data-sc-tab]/@href')
        self.assertTrue(hrefs)
        for href in hrefs:
            self.assertIn('sc_from=' + _q(self.player_url), href)
            self.assertNotIn('sc_clock', href)
        back, _crumbs, _current, _context = self._nav(
            '/my/activities?sc_from=%s&tab=all' % _q(self.player_url))
        self.assertEqual(back, [self.player_url])

    # -- UC-C4 -----------------------------------------------------------
    def test_untrusted_origin_is_ignored(self):
        for bad in ('https://evil.example/my/home', '//evil.example/my/home',
                    'javascript:alert(1)', '/\\evil.example', '/my/home\tx'):
            url = CLOCK + '&sc_from=' + _q(bad)
            back, crumbs, _current, _context = self._nav(url)
            self.assertEqual((back, crumbs), ([], []), bad)
            self.assertEqual(self._clock_href(url), CLOCK, bad)

    def test_unregistered_or_unreadable_origin_goes_home(self):
        unreadable = '/my/player?player_id=%s' % self.player_c.id
        for origin in ('/web/login', '/my/account', unreadable):
            back, crumbs, _current, _context = self._nav(CLOCK + '&sc_from=' + _q(origin))
            self.assertEqual(back, [HOME], origin)
            self.assertEqual(crumbs, [(HOME, 'Home')], origin)

    # -- UC-C5 -----------------------------------------------------------
    def test_record_wrappers_keep_their_parent(self):
        url = '/my/team/activities?team_id=%s&sc_from=%s' % (self.team_a.id, _q(HOME))
        back, _crumbs, _current, _context = self._nav(url)
        self.assertEqual(back, [self.team_url + '&tab=activities'])
