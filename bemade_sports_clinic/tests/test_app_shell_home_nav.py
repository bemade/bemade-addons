"""App shell home polish (owner review on staging, 2026-10-10). Synthetic
fixtures only.

Acceptance criteria covered here:

* UC-H2 An event opened from the home's « Upcoming » card comes back to the
  home: the link carries ``return_url=/my/home`` and the event page's back
  chevron (and crumb) point to ``/my/home``, not to the events list.
* UC-H3 The home's « Calendar » link opens the events list with
  ``return_url=/my/home``: the list's back chevron points to the home, the
  segments (upcoming · past · calendar) and type chips keep it, and the
  calendar page's back chevron points to the home too (the return URL is not
  sent to the calendar feed). Without it, both pages still go back to
  « More ».
* UC-H5 The « Teams » tab / rail entry (and the installed app's shortcut)
  opens the full teams list ``/my/teams``, a top-level page (logo, no back
  chevron, « Teams » current). The dashboard (``/my/home``) stays the login
  landing page, reached from the logo. « Teams » crumbs on the team, player
  and digest pages point to ``/my/teams``.
* UC-H6 The « Players » list (``/my/players``) shows the most injured first
  — out, then returning, then available — alphabetical within each group
  (the roster's « By status » order) by default. A switch toggles it to
  alphabetical and back; the choice is sticky per user
  (``res.users.players_sort_mode``) and the switch keeps the active filters.
* UC-H7 Phone bottom tabs: « Teams », « Players », « Notepad » (therapists),
  « Activities », then « More » — « Clinic », « Events » and « Timesheets »
  move to « More ». Laptop rail: the same plus « Clinic », « Events »,
  « Timesheets » always visible above « More ».
* UC-H8 Team page: the digest-history sheet's lazy body is themed as a
  legacy fragment (was white rows with light text in the dark theme).
* UC-H4 A ``return_url`` that is not a local path is ignored (no open
  redirect through the back chevron).
"""
import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common

HOME = '/my/home'


@tagged('post_install', '-at_install')
class TestAppShellHomeNav(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start = fields.Datetime.now() + timedelta(days=1)
        cls.upcoming = cls.env['sports.event'].create({
            'name': 'SC Home Nav Practice',
            'event_type': 'practice',
            'date_start': start,
            'date_end': start + timedelta(hours=2),
            'team_ids': [Command.set([cls.team_a.id])],
        })

    def setUp(self):
        super().setUp()
        self._switch(True)
        self._login_tp()

    @staticmethod
    def _back(tree):
        return tree.xpath('//a[contains(concat(" ", @class, " "), " o_sc_back ")]/@href')

    @staticmethod
    def _return_url(href):
        return parse_qs(urlparse(href).query).get('return_url', [None])[0]

    # -- UC-H2 -----------------------------------------------------------
    def test_upcoming_event_comes_back_home(self):
        _text, tree = self._get(HOME)
        hrefs = tree.xpath('//*[@data-sc-section="home.upcoming"]//a/@href')
        href = [h for h in hrefs if h.startswith('/my/event/%s' % self.upcoming.id)]
        self.assertEqual(len(href), 1, hrefs)
        self.assertEqual(self._return_url(href[0]), HOME)
        _text, tree = self._get(href[0])
        self.assertEqual(self._back(tree), [HOME])

    def test_upcoming_event_crumb_comes_back_home(self):
        self.tp.sc_nav_mode = 'crumbs'
        _text, tree = self._get('/my/event/%s?return_url=%%2Fmy%%2Fhome' % self.upcoming.id)
        self.assertIn(HOME, tree.xpath('//nav[contains(@class, "o_sc_crumbs")]//a/@href'))

    def test_event_from_list_still_goes_back_to_list(self):
        _text, tree = self._get('/my/event/%s' % self.upcoming.id)
        self.assertEqual(self._back(tree), ['/my/events'])

    # -- UC-H3 -----------------------------------------------------------
    def test_calendar_link_comes_back_home(self):
        _text, tree = self._get(HOME)
        more = tree.xpath('//*[@data-sc-section="home.upcoming"]'
                          '//a[starts-with(@href, "/my/events")]/@href')
        self.assertEqual(len(more), 1, more)
        self.assertEqual(self._return_url(more[0]), HOME)
        _text, tree = self._get(more[0])
        self.assertEqual(self._back(tree), [HOME])
        segments = dict(zip(tree.xpath('//nav[@data-sc-tabs]//a/@data-sc-tab'),
                            tree.xpath('//nav[@data-sc-tabs]//a/@href')))
        for key in ('upcoming', 'past', 'calendar'):
            self.assertEqual(self._return_url(segments[key]), HOME, key)
        for chip in tree.xpath('//a[@data-sc-event-type]/@href'):
            self.assertEqual(self._return_url(chip), HOME, chip)
        _text, tree = self._get(segments['calendar'])
        self.assertEqual(self._back(tree), [HOME])
        node = tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_calendar"]')[0]
        self.assertNotIn('return_url', json.loads(node.get('props'))['params'])
        segments = dict(zip(tree.xpath('//nav[@data-sc-tabs]//a/@data-sc-tab'),
                            tree.xpath('//nav[@data-sc-tabs]//a/@href')))
        for key in ('upcoming', 'past'):
            self.assertEqual(self._return_url(segments[key]), HOME, key)

    def test_events_without_return_url_go_back_to_more(self):
        for url in ('/my/events', '/my/events/calendar'):
            _text, tree = self._get(url)
            self.assertEqual(self._back(tree), ['/my/app/more'], url)

    # -- UC-H4 -----------------------------------------------------------
    def test_foreign_return_url_ignored(self):
        for bad in ('https://evil.example', '//evil.example', 'javascript:alert(1)'):
            for url in ('/my/events', '/my/events/calendar'):
                _text, tree = self._get('%s?return_url=%s' % (url, bad))
                self.assertEqual(self._back(tree), ['/my/app/more'], (url, bad))

    # -- UC-H5 -----------------------------------------------------------
    def _nav_hrefs(self, tree, key):
        return tree.xpath('//nav[contains(@class, "o_sc_tabs") or contains(@class, "o_sc_rail_nav")]'
                          '//a[@data-sc-nav-key="%s"]/@href' % key)

    def test_teams_nav_opens_teams_list(self):
        _text, tree = self._get(HOME)
        hrefs = self._nav_hrefs(tree, 'teams')
        self.assertTrue(hrefs)
        self.assertEqual(set(hrefs), {'/my/teams'})
        self.assertIn(HOME, tree.xpath('//a[contains(@class, "o_sc_logo") or contains(@class, "o_sc_rail_brand")]/@href'))
        _text, tree = self._get('/my/teams')
        self.assertEqual(self._back(tree), [])
        self.assertTrue(tree.xpath('//a[contains(@class, "o_sc_logo")][@href="%s"]' % HOME))
        current = tree.xpath('//nav[contains(@class, "o_sc_rail_nav")]//a[@aria-current="page"]/@data-sc-nav-key')
        self.assertEqual(current, ['teams'])

    def test_team_crumbs_point_to_teams_list(self):
        self.tp.sc_nav_mode = 'crumbs'
        _text, tree = self._get('/my/team?team_id=%s' % self.team_a.id)
        crumbs = tree.xpath('//nav[contains(@class, "o_sc_crumbs")]//a/@href')
        self.assertIn('/my/teams', crumbs)
        self.assertNotIn(HOME, crumbs)

    # -- UC-H6 -----------------------------------------------------------
    def _make_order_players(self):
        Patient = self.env['sports.patient']
        made = {}
        for last, match, practice in (('Aaa', 'yes', 'yes'), ('Zzz', 'no', 'no'),
                                      ('Mmm', 'no', 'yes'), ('Bbb', 'no', 'no')):
            made[last] = Patient.create({
                'first_name': 'Order', 'last_name': last,
                'match_status': match, 'practice_status': practice,
                'team_ids': [Command.set([self.team_a.id])],
            })
        return made

    @staticmethod
    def _player_ids(tree):
        return [int(x) for x in tree.xpath(
            '//*[@data-sc-section="players.list"]//*[@data-sc-player-id]/@data-sc-player-id')]

    @staticmethod
    def _sort_switch(tree):
        nodes = tree.xpath('//a[@role="switch"][@data-sc-section="players.sort"]')
        return nodes[0] if nodes else None

    def test_players_list_most_injured_first(self):
        made = self._make_order_players()
        _text, tree = self._get('/my/players?first_name=Order')
        self.assertEqual(self._player_ids(tree), [made[k].id for k in ('Bbb', 'Zzz', 'Mmm', 'Aaa')])
        switch = self._sort_switch(tree)
        self.assertIsNotNone(switch)
        self.assertEqual(switch.get('aria-checked'), 'true')
        args = parse_qs(urlparse(switch.get('href')).query)
        self.assertEqual(args.get('sort'), ['name'])
        self.assertEqual(args.get('first_name'), ['Order'])

    def test_players_sort_toggle_is_sticky(self):
        made = self._make_order_players()
        alpha = [made[k].id for k in ('Aaa', 'Bbb', 'Mmm', 'Zzz')]
        _text, tree = self._get('/my/players?first_name=Order&sort=name')
        self.assertEqual(self._player_ids(tree), alpha)
        self.env.invalidate_all()
        self.assertEqual(self.tp.players_sort_mode, 'name')
        switch = self._sort_switch(tree)
        self.assertEqual(switch.get('aria-checked'), 'false')
        self.assertEqual(parse_qs(urlparse(switch.get('href')).query).get('sort'), ['status'])
        # Sticky: the next visit without ?sort= keeps alphabetical.
        _text, tree = self._get('/my/players?first_name=Order')
        self.assertEqual(self._player_ids(tree), alpha)
        # Back to most injured first.
        _text, tree = self._get('/my/players?first_name=Order&sort=status')
        self.assertEqual(self._player_ids(tree), [made[k].id for k in ('Bbb', 'Zzz', 'Mmm', 'Aaa')])
        self.env.invalidate_all()
        self.assertEqual(self.tp.players_sort_mode, 'status')

    # -- UC-H7 -----------------------------------------------------------
    def test_phone_tabs_and_laptop_rail(self):
        _text, tree = self._get('/my/teams')
        self.assertEqual(self._nav_keys(tree, 'o_sc_tabs'),
                         ['teams', 'players', 'notepad', 'activities', 'more'])
        self.assertEqual(self._nav_keys(tree, 'o_sc_rail_nav'),
                         ['teams', 'players', 'notepad', 'activities',
                          'clinic', 'events', 'timesheets', 'more'])
        _text, tree = self._get('/my/app/more')
        plus = tree.xpath('//main[@id="sc_content"]//a/@data-sc-nav-key')
        for key in ('clinic', 'events', 'timesheets'):
            self.assertIn(key, plus, key)
        for key in ('teams', 'players', 'notepad', 'activities'):
            self.assertNotIn(key, plus, key)
        # Already on the laptop rail: marked so « More » hides them there.
        railed = tree.xpath('//main[@id="sc_content"]//a[@data-sc-in-rail]/@data-sc-nav-key')
        self.assertEqual(set(railed), {'clinic', 'events', 'timesheets'})

    def test_coach_tabs_and_rail(self):
        self._login_coach()
        _text, tree = self._get('/my/teams')
        self.assertEqual(self._nav_keys(tree, 'o_sc_tabs'),
                         ['teams', 'players', 'activities', 'more'])
        self.assertEqual(self._nav_keys(tree, 'o_sc_rail_nav'),
                         ['teams', 'players', 'activities', 'events', 'more'])
        _text, tree = self._get('/my/app/more')
        self.assertIn('events', tree.xpath('//main[@id="sc_content"]//a/@data-sc-nav-key'))

    # -- UC-H8 -----------------------------------------------------------
    def test_digest_history_sheet_body_is_themed(self):
        _text, tree = self._get('/my/team?team_id=%s' % self.team_a.id)
        body = tree.xpath('//dialog[@id="sc_digest_history_sheet"]'
                          '//*[contains(@class, "o_sc_sheet_body")]')
        self.assertEqual(len(body), 1)
        self.assertIn('o_sc_legacy', body[0].get('class').split())
