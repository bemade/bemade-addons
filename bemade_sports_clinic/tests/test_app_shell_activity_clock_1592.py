"""Task 1592 (portal app P3) — the activity clock in the app bar and the
clock counts on player / team / event rows and injury cards. Synthetic
fixtures only (this repository is public).

Acceptance criteria (owner decisions 2026-10-13, with MC):

* UC-1 App bar: a clock icon (the slot the theme toggle left, #1602) for
  the staff roles; tap → /my/activities (« Mine ») from the clock. Its red
  badge = MY overdue activities, NOT computed on the page: a hidden badge
  wired to sc_live_count.js (eager first fetch, hidden at 0). When the
  theme choice is on, the toggle and the clock both render. No count badge
  on the Activities menu item.
* UC-2 The count route /my/activities/overdue/count answers {count: N}:
  activities assigned to ME, overdue (deadline before today), in my team
  scope — the « My Activities » domain; others' activities and records
  outside my teams are not counted; never cached; a user without a staff
  app role is refused (403).
* UC-3 The activities page opened from the clock lands on the Overdue tab
  when I have overdue activities, on All otherwise; an explicit ?tab= wins;
  the tab links do not carry the clock marker.
* UC-4 Player rows (team roster, /my/players), team rows (home, /my/teams),
  event rows (/my/events) and injury cards (player page, clinic dossier)
  show a clock chip with the number of activities assigned to ME on that
  record (an injury: the patient-scoped activities about it); red when at
  least one is overdue, neutral otherwise; hidden at 0. Another user's
  activities are never counted.
* UC-5 The chip opens the record's own activities: the player page's
  Activities tab (team / clinic context kept), the team page's Activities
  tab, the event's activities page; an injury (no activities of its own,
  task 1409) opens its player's Activities tab. No <a> inside an <a>.
* UC-6 One grouped query per list: the clock counts cost ONE mail.activity
  _read_group per list, and a 40-row list costs about the same number of
  queries as a 5-row one.
* UC-7 French (fr_CA): the chip's label and the app bar strings render
  translated.
"""
import logging
from datetime import timedelta
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

_logger = logging.getLogger(__name__)

COUNT_URL = '/my/activities/overdue/count'


def _text(node):
    return ' '.join(node.text_content().split())


class Clock1592Mixin:

    def _activity(self, record, user, days=0, summary='Synthetic clock task', **extra):
        """An activity on ``record`` for ``user``, due ``days`` from today
        (negative = overdue)."""
        env = self.env
        return env['mail.activity'].create({
            'res_model_id': env['ir.model']._get(record._name).id,
            'res_id': record.id,
            'activity_type_id': env.ref('mail.mail_activity_data_todo').id,
            'summary': summary,
            'user_id': user.id,
            'date_deadline': fields.Date.today() + timedelta(days=days),
            **extra,
        })

    @staticmethod
    def _clock(node):
        clocks = node.xpath('.//a[contains(@class, "o_sc_activity_clock")]')
        return clocks[0] if clocks else None

    def _assert_clock(self, node, count, overdue, href):
        clock = self._clock(node)
        self.assertIsNotNone(clock, 'no clock chip')
        self.assertEqual(clock.get('data-sc-activity-clock'), str(count))
        self.assertEqual(clock.get('data-sc-activity-overdue'), str(overdue))
        self.assertEqual(_text(clock), str(count))
        self.assertIn('o_sc_chip_red' if overdue else 'o_sc_chip_ghost', clock.get('class'))
        self.assertNotIn('o_sc_chip_ghost' if overdue else 'o_sc_chip_red', clock.get('class'))
        self.assertEqual(clock.get('href'), href)
        self.assertTrue(clock.get('aria-label'))
        return clock


class Clock1592Common(Clock1592Mixin, AppShellCommon):
    """Base fixtures (portal_cov_common): the therapist holds a To-Do on the
    player, one about the injury (patient-scoped, injury_id), one on team A
    and one on the event — all due today (not overdue)."""


@tagged('post_install', '-at_install')
class TestActivityClockAppBar1592(Clock1592Common):

    # -- UC-1 ------------------------------------------------------------
    def test_app_bar_clock(self):
        self._switch(True)
        for login in (self._login_tp, self._login_coach):
            login()
            text, tree = self._get('/my/home')
            bar = tree.xpath('//header[contains(@class, "o_sc_appbar")]'
                             '//a[@data-sc-activity-clock-bar]')
            self.assertEqual(len(bar), 1)
            # Task 1622: the href carries the page it is tapped on.
            self.assertEqual(bar[0].get('href'), '/my/activities?sc_clock=1&sc_from=%2Fmy%2Fhome')
            self.assertEqual(bar[0].get('title'), 'My activities')
            badge = bar[0].xpath('.//*[@data-sc-live-count-url]')[0]
            self.assertEqual(badge.get('data-sc-live-count-url'), COUNT_URL)
            self.assertEqual(badge.get('data-sc-live-eager'), '1')
            self.assertEqual(badge.get('data-sc-live-hide-zero'), '1')
            # Not computed on the page: hidden until the first fetch.
            self.assertEqual(badge.get('hidden'), 'hidden')
            self.assertEqual(_text(badge), '0')
            # No count badge on the Activities menu item.
            for item in tree.xpath('//a[@data-sc-nav-key="activities"]'):
                self.assertFalse(item.xpath('.//*[contains(@class, "o_sc_chip")]'
                                            ' | .//*[@data-sc-live-count-url]'))
                self.assertFalse(any(ch.isdigit() for ch in _text(item)))

    def test_app_bar_clock_next_to_theme_toggle(self):
        self._switch(True)
        self._theme_choice(True)
        self._login_tp()
        _text_, tree = self._get('/my/home')
        header = tree.xpath('//header[contains(@class, "o_sc_appbar")]')[0]
        self.assertTrue(header.xpath('.//form[contains(@class, "o_sc_theme_toggle")]'))
        self.assertTrue(header.xpath('.//a[@data-sc-activity-clock-bar]'))

    # -- UC-2 ------------------------------------------------------------
    def test_count_route(self):
        self._login_tp()
        resp = self.url_open(COUNT_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('no-store', resp.headers.get('Cache-Control', ''))
        self.assertEqual(resp.json(), {'count': 0})  # all due today
        self._activity(self.team_a, self.tp, days=-3)
        self._activity(self.player, self.tp, days=-1)
        self._activity(self.event, self.tp, days=2)  # upcoming: not counted
        self.assertEqual(self.url_open(COUNT_URL).json(), {'count': 2})
        # Another user's overdue activity is not mine.
        self._activity(self.team_a, self.coach, days=-3)
        # Mine, overdue, but on a team I do not staff: out of « My Activities ».
        self._activity(self.team_b, self.tp, days=-3)
        self.assertEqual(self.url_open(COUNT_URL).json(), {'count': 2})
        # The coach counts their own.
        self._login_coach()
        self.assertEqual(self.url_open(COUNT_URL).json(), {'count': 1})

    def test_count_route_refused_without_staff_role(self):
        self._login_plain()
        with mute_logger('odoo.http'):
            resp = self.url_open(COUNT_URL)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json(), {'error': 'forbidden'})

    # -- UC-3 ------------------------------------------------------------
    def _active_tab(self, tree):
        return tree.xpath('//section[@data-sc-tab-panel][not(@hidden)]/@data-sc-tab-panel')

    def test_activities_page_from_clock(self):
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get('/my/activities?sc_clock=1')
        self.assertEqual(self._active_tab(tree), ['all'])
        late = self._activity(self.player, self.tp, days=-2, summary='Synthetic late task')
        _text_, tree = self._get('/my/activities?sc_clock=1')
        self.assertEqual(self._active_tab(tree), ['overdue'])
        panel = tree.xpath('//section[@data-sc-tab-panel="overdue"]')[0]
        self.assertEqual([int(x) for x in panel.xpath('.//@data-sc-activity-row')], [late.id])
        # The tab links do not carry the clock marker; an explicit tab wins.
        hrefs = tree.xpath('//a[@data-sc-tab]/@href')
        self.assertTrue(hrefs)
        self.assertFalse([h for h in hrefs if 'sc_clock' in h])
        _text_, tree = self._get('/my/activities?sc_clock=1&tab=planned')
        self.assertEqual(self._active_tab(tree), ['planned'])
        # Without the marker: unchanged (All).
        _text_, tree = self._get('/my/activities')
        self.assertEqual(self._active_tab(tree), ['all'])


@tagged('post_install', '-at_install')
class TestActivityClockRows1592(Clock1592Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _player_row(self, tree, section):
        rows = tree.xpath('//*[@data-sc-section="%s"]//*[contains(@class, "o_sc_player_row")]'
                          '[@data-sc-player-id="%s"]' % (section, self.player.id))
        self.assertTrue(rows, 'no row for the player in %s' % section)
        return rows[0]

    # -- UC-4 / UC-5: player rows ----------------------------------------
    def test_player_row_clock(self):
        self._login_tp()
        team_url = '/my/team?team_id=%s' % self.team_a.id
        _text_, tree = self._get(team_url + '&tab=players')
        row = self._player_row(tree, 'team.roster')
        # act_player + act_injury, both mine, none overdue.
        href = '/my/player?player_id=%s&team_id=%s&tab=activities' % (self.player.id, self.team_a.id)
        self._assert_clock(row, 2, 0, href)
        self.assertFalse(row.xpath('.//a//a'))
        # Someone else's activity does not count; my overdue one turns it red.
        self._activity(self.player, self.coach, days=-5)
        self._activity(self.player, self.tp, days=-1)
        _text_, tree = self._get(team_url + '&tab=players')
        self._assert_clock(self._player_row(tree, 'team.roster'), 3, 1, href)
        # /my/players: no team context.
        _text_, tree = self._get('/my/players')
        row = tree.xpath('//*[contains(@class, "o_sc_player_row")][@data-sc-player-id="%s"]'
                         % self.player.id)[0]
        self._assert_clock(row, 3, 1, '/my/player?player_id=%s&tab=activities' % self.player.id)

    def test_player_row_zero_hidden_and_per_user(self):
        healthy = self.env['sports.patient'].create({
            'first_name': 'Nia', 'last_name': 'Noclock',
            'team_ids': [Command.set([self.team_a.id])],
        })
        self._activity(healthy, self.tp, days=-1)  # the therapist's, not the coach's
        self._login_coach()
        _text_, tree = self._get('/my/team?team_id=%s&tab=players' % self.team_a.id)
        for player in (self.player, healthy):
            row = tree.xpath('//*[@data-sc-section="team.roster"]//*[contains(@class, "o_sc_player_row")]'
                             '[@data-sc-player-id="%s"]' % player.id)[0]
            self.assertIsNone(self._clock(row), 'the coach has no activity on %s' % player.name)
        self._activity(healthy, self.coach)
        _text_, tree = self._get('/my/team?team_id=%s&tab=players' % self.team_a.id)
        row = tree.xpath('//*[@data-sc-section="team.roster"]//*[contains(@class, "o_sc_player_row")]'
                         '[@data-sc-player-id="%s"]' % healthy.id)[0]
        self._assert_clock(row, 1, 0, '/my/player?player_id=%s&team_id=%s&tab=activities'
                           % (healthy.id, self.team_a.id))

    # -- team rows ---------------------------------------------------------
    def test_team_row_clock(self):
        self._login_tp()
        href = '/my/team?team_id=%s&tab=activities' % self.team_a.id
        # Task 1624 (deliberate update): « My teams » left the home.
        for url in ('/my/teams',):
            _text_, tree = self._get(url)
            main = tree.xpath('//a[@data-sc-team-id="%s"]' % self.team_a.id)
            self.assertEqual(len(main), 1, url)
            self.assertIn('o_sc_link_row_main', main[0].get('class'))
            row = main[0].xpath('ancestor::*[contains(@class, "o_sc_link_row")][1]')[0]
            self._assert_clock(row, 1, 0, href)  # act_team
            self.assertFalse(row.xpath('.//a//a'))
        self._activity(self.team_a, self.tp, days=-4)
        _text_, tree = self._get('/my/teams')
        row = tree.xpath('//a[@data-sc-team-id="%s"]/ancestor::*[contains(@class, "o_sc_link_row")][1]'
                         % self.team_a.id)[0]
        self._assert_clock(row, 2, 1, href)
        # The coach has none on the team: no chip.
        self._login_coach()
        _text_, tree = self._get('/my/teams')
        row = tree.xpath('//a[@data-sc-team-id="%s"]/ancestor::*[contains(@class, "o_sc_link_row")][1]'
                         % self.team_a.id)[0]
        self.assertIsNone(self._clock(row))

    # -- event rows --------------------------------------------------------
    def test_event_row_clock(self):
        self._activity(self.event, self.tp, days=-1)
        self._login_tp()
        _text_, tree = self._get('/my/events?no_default_dates=1')
        main = tree.xpath('//*[@data-sc-section="events.list"]//a[@data-sc-event-id="%s"]' % self.event.id)[0]
        self.assertIn('o_sc_link_row_main', main.get('class'))
        row = main.xpath('ancestor::*[contains(@class, "o_sc_link_row")][1]')[0]
        self._assert_clock(row, 2, 1, '/my/event/activities?event_id=%s' % self.event.id)
        self.assertFalse(row.xpath('.//a//a'))
        # The target page lists the event's activities.
        resp = self.url_open('/my/event/activities?event_id=%s' % self.event.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Event task', resp.text)
        # The coach has none on the event.
        self._login_coach()
        _text_, tree = self._get('/my/events?no_default_dates=1')
        row = tree.xpath('//*[@data-sc-section="events.list"]//a[@data-sc-event-id="%s"]'
                         '/ancestor::*[contains(@class, "o_sc_link_row")][1]' % self.event.id)[0]
        self.assertIsNone(self._clock(row))

    # -- injury cards (player page) ----------------------------------------
    def test_injury_card_clock_player_page(self):
        other = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic quiet injury',
        })
        other.with_context(mail_notrack=True).write({'stage': 'active'})
        self._login_tp()
        url = '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)
        _text_, tree = self._get(url)
        card = tree.xpath('//details[@id="injury-%s"]' % self.injury.id)[0]
        # act_injury only (act_player is not about this injury).
        clock = self._assert_clock(card, 1, 0, url + '&tab=activities')
        # In the summary row, beside the status chip.
        self.assertTrue(clock.xpath('ancestor::summary'))
        quiet = tree.xpath('//details[@id="injury-%s"]' % other.id)[0]
        self.assertIsNone(self._clock(quiet))
        # The target tab lists the injury's activity.
        _text_, tree = self._get(url + '&tab=activities')
        panel = tree.xpath('//section[@data-sc-tab-panel="activities"]')[0]
        self.assertIsNone(panel.get('hidden'))
        self.assertIn('Injury task', _text(panel))


@tagged('post_install', '-at_install')
class TestActivityClockDossier1592(Clock1592Mixin, Clinic1540Common):

    def test_injury_card_clock_dossier(self):
        self._switch(True)
        self._activity(self.player, self.tp, days=-2, injury_id=self.injury.id)
        self._login_tp()
        _text_, tree = self._get('/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player.id))
        card = tree.xpath('//details[@id="clinic-injury-%s"]' % self.injury.id)[0]
        self._assert_clock(card, 2, 1, '/my/player?player_id=%s&clinic_id=%s&team_id=%s&tab=activities'
                           % (self.player.id, self.clinic.id, self.team_a.id))


@tagged('post_install', '-at_install')
class TestActivityClockQueries1592(Clock1592Common):
    """UC-6: one grouped query per list, bounded cost."""

    def _fill(self, team, count, start):
        env = self.env
        other = env['sports.team'].create({'name': 'Clock Other %s' % start, 'parent_id': self.org.id})
        for n in range(count):
            player = env['sports.patient'].create({
                'first_name': 'Synthetic', 'last_name': 'Clock %03d' % (start + n),
                'team_ids': [Command.set([team.id, other.id])],
            })
            injury = env['sports.patient.injury'].create({
                'patient_id': player.id, 'diagnosis': 'Synthetic clock %s' % n,
            })
            injury.with_context(mail_notrack=True).write({'stage': 'active'})
            self._activity(player, self.tp, days=-1 if n % 2 else 1)
            self._activity(player, self.tp, days=0, injury_id=injury.id)

    def _measure(self, url):
        """(queries, clock read_groups) of one warm GET of ``url``."""
        Activity = type(self.env['mail.activity'])
        orig = Activity._read_group
        calls = []

        def spy(self_, domain, groupby=(), aggregates=(), *args, **kwargs):
            if 'date_deadline:day' in tuple(groupby):
                calls.append(tuple(groupby))
            return orig(self_, domain, groupby, aggregates, *args, **kwargs)

        self.env.flush_all()
        self.env.invalidate_all()
        self.url_open(url)  # warm-up (assets, session, caches)
        self.env.flush_all()
        self.env.invalidate_all()
        with patch.object(Activity, '_read_group', spy):
            before = self.cr.sql_log_count
            resp = self.url_open(url)
            queries = self.cr.sql_log_count - before
        self.assertEqual(resp.status_code, 200, url)
        return queries, len(calls)

    def test_one_grouped_query_per_list(self):
        self._switch(True)
        small = self.env['sports.team'].create({'name': 'Clock Small', 'parent_id': self.org.id})
        big = self.env['sports.team'].create({'name': 'Clock Big', 'parent_id': self.org.id})
        for team in (small, big):
            self.env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': self.tp.partner_id.id, 'role': 'therapist',
            })
            self._activity(team, self.tp, days=-1)
        self._fill(small, 5, 0)
        self._fill(big, 40, 100)
        self._login_tp()
        for template in ('/my/team?team_id=%s&tab=players', '/my/players?team_id=%s'):
            q_small, rg_small = self._measure(template % small.id)
            q_big, rg_big = self._measure(template % big.id)
            _logger.info("1592 %s: 5 rows %s queries, 40 rows %s", template, q_small, q_big)
            # The player rows' clocks: ONE grouped query for the whole list.
            self.assertEqual((rg_small, rg_big), (1, 1), template)
            self.assertLess(q_big - q_small, 10, '%s: %s vs %s' % (template, q_small, q_big))
        # The teams list, the home and the events list: one each.
        for url in ('/my/teams', '/my/events?no_default_dates=1'):
            _queries, groups = self._measure(url)
            self.assertEqual(groups, 1, url)
        # Task 1624 review round 1: the home's « À faire » reads the activity
        # cards themselves (ONE search for its fold-outs), no grouped count.
        _queries, groups = self._measure('/my/home')
        self.assertLessEqual(groups, 1, '/my/home')
        # The player page's injury cards: one.
        player = self.env['sports.patient'].search([('last_name', '=', 'Clock 100')])
        _queries, groups = self._measure('/my/player?player_id=%s' % player.id)
        self.assertEqual(groups, 1)


@tagged('post_install', '-at_install')
class TestActivityClockI18n1592(Clock1592Mixin, TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_clock_in_french(self):
        self._activity(self.team_a, self.tp, days=-2)
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr('/my/teams'))
        bar = tree.xpath('//a[@data-sc-activity-clock-bar]')[0]
        self.assertEqual(bar.get('title'), 'Mes activités')
        self.assertEqual(bar.xpath('.//*[@data-sc-live-count-url]')[0].get('title'),
                         'Activités en retard')
        row = tree.xpath('//a[@data-sc-team-id="%s"]/ancestor::*[contains(@class, "o_sc_link_row")][1]'
                         % self.team_a.id)[0]
        clock = self._clock(row)
        self.assertEqual(clock.get('aria-label'), 'Mes activités : 2 (1 en retard)')
        tree = lxml_html.fromstring(self._fr('/my/team?team_id=%s&tab=players' % self.team_a.id))
        row = tree.xpath('//*[contains(@class, "o_sc_player_row")][@data-sc-player-id="%s"]'
                         % self.player.id)[0]
        self.assertEqual(self._clock(row).get('aria-label'), 'Mes activités : 2')
