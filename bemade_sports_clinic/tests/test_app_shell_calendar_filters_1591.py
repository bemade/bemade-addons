"""Task 1591 (portal app, gap G8) — the events calendar gets the list's
filters, and both pages keep them when switching from one to the other.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 The feed (/my/events/calendar/data) honours every filter the bar
  exposes: event type (new), team, organization, assigned professional,
  views (« My events » / « Unassigned »), « Show cancelled » and the list's
  free-text ``search`` (new). An unknown event type is ignored.
* UC-2 The calendar page shows the list's filter bar — type chips, view
  chips, organization / team / professional / « Show cancelled » — posting
  back to the calendar, without the list-only fields (dates, sort, group
  by); the current filters are selected and handed to the calendar
  component (its feed params). A stale ``date_from`` / ``date_to`` in the
  calendar URL is not forwarded to the feed.
* UC-3 The URL carries the filters both ways: the list's « Calendar »
  segment keeps the filters but never the list's own parameters (default
  « from today », explicit dates, sort, group by, page, segment); the
  calendar's « Upcoming » / « Past » segments keep the filters; the
  calendar's chips stay on the calendar and keep the other filters.
* UC-4 Tour (phone + laptop): filter the list -> open the calendar -> the
  same filters are active and only the matching event is shown -> filter
  the calendar on its own (a type chip) -> back to the list, which keeps
  the calendar's filters.
* UC-5 French (fr_CA): the calendar's filter bar (the shared template's
  terms) and its view chips render translated.
"""
import json
import urllib.parse
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from lxml import html as lxml_html

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class Calendar1591Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.org_z = env['res.partner'].create({'name': 'ZZ Org 1591', 'is_company': True})
        cls.team_c = env['sports.team'].create({'name': 'ZZ Team C 1591', 'parent_id': cls.org_z.id})
        env['sports.team.staff'].create({
            'team_id': cls.team_c.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist'})
        start = fields.Datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
        Event = env['sports.event']

        def _event(name, kind, team, staff=None, state=None):
            event = Event.create({
                'name': name, 'event_type': kind, 'team_ids': [Command.set([team.id])],
                'date_start': start, 'date_end': start + timedelta(hours=2),
                'assigned_staff_ids': [Command.set(staff.ids if staff else [])],
            })
            if state:
                event.write({'state': state})
            return event

        cls.ev_game_a = _event('SC 1591 Game A', 'game', cls.team_a, staff=cls.tp)
        cls.ev_practice_a = _event('SC 1591 Practice A lighthouse', 'practice', cls.team_a)
        cls.ev_game_c = _event('SC 1591 Game C', 'game', cls.team_c)
        cls.ev_cancel_a = _event('SC 1591 Cancelled A', 'game', cls.team_a, state='cancelled')
        cls.ours = {cls.ev_game_a.id, cls.ev_practice_a.id, cls.ev_game_c.id, cls.ev_cancel_a.id}
        cls.window = 'start=%s&end=%s' % (
            urllib.parse.quote((start - timedelta(days=2)).isoformat() + 'Z'),
            urllib.parse.quote((start + timedelta(days=2)).isoformat() + 'Z'))


@tagged('post_install', '-at_install')
class TestCalendarFilters1591(Calendar1591Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _feed(self, query=''):
        url = '/my/events/calendar/data?%s%s' % (self.window, '&' + query if query else '')
        return {row['id'] for row in self.url_open(url).json()} & self.ours

    @staticmethod
    def _query(url):
        return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))

    @staticmethod
    def _segment(tree, key):
        return tree.xpath('//nav[@data-sc-tabs]//a[@data-sc-tab="%s"]/@href' % key)[0]

    # -- UC-1 ------------------------------------------------------------
    def test_feed_honours_each_filter(self):
        self._login_tp()
        everything = {self.ev_game_a.id, self.ev_practice_a.id, self.ev_game_c.id}
        self.assertEqual(self._feed(), everything)
        self.assertEqual(self._feed('event_type=game'), {self.ev_game_a.id, self.ev_game_c.id})
        self.assertEqual(self._feed('event_type=practice'), {self.ev_practice_a.id})
        self.assertEqual(self._feed('event_type=bogus'), everything)
        self.assertEqual(self._feed('team_id=%s' % self.team_c.id), {self.ev_game_c.id})
        self.assertEqual(self._feed('organization_id=%s' % self.org.id),
                         {self.ev_game_a.id, self.ev_practice_a.id})
        self.assertEqual(self._feed('assigned_user_id=%s' % self.tp.id), {self.ev_game_a.id})
        self.assertEqual(self._feed('view_type=my'), {self.ev_game_a.id})
        self.assertEqual(self._feed('view_type=unassigned'), {self.ev_practice_a.id, self.ev_game_c.id})
        self.assertEqual(self._feed('show_cancelled=1&team_id=%s&event_type=game' % self.team_a.id),
                         {self.ev_game_a.id, self.ev_cancel_a.id})
        self.assertEqual(self._feed('search=lighthouse'), {self.ev_practice_a.id})
        self.assertEqual(self._feed('search=%s' % urllib.parse.quote('ZZ Team C')), {self.ev_game_c.id})

    # -- UC-2 ------------------------------------------------------------
    def test_calendar_has_the_filter_bar(self):
        self._login_tp()
        _text, tree = self._get(
            '/my/events/calendar?event_type=game&team_id=%s&show_cancelled=1&search=lighthouse'
            '&date_from=2000-01-01&date_to=2000-01-31&sortby=name' % self.team_a.id)
        chips = tree.xpath('//*[@data-sc-section="events.types"]//a[@aria-pressed="true"]/@data-sc-event-type')
        self.assertEqual(chips, ['game'])
        views = tree.xpath('//*[@data-sc-section="events.views"]//a/@data-sc-view')
        self.assertEqual(views, ['all', 'my', 'unassigned', 'missing_timesheets'])
        form = tree.xpath('//form[@data-sc-section="events.filters"]')[0]
        self.assertEqual(form.get('action'), '/my/events/calendar')
        names = set(form.xpath('.//*[@name]/@name'))
        for name in ('organization_id', 'team_id', 'assigned_user_id', 'show_cancelled',
                     'event_type', 'view_type', 'search'):
            self.assertIn(name, names)
        for name in ('date_from', 'date_to', 'sortby', 'group_by', 'segment', 'no_default_dates'):
            self.assertNotIn(name, names)
        self.assertEqual(form.xpath('.//select[@name="team_id"]/option[@selected]/@value'), [str(self.team_a.id)])
        self.assertEqual(form.xpath('.//input[@name="show_cancelled"]/@checked'), ['checked'])
        self.assertEqual(form.xpath('.//input[@name="event_type"]/@value'), ['game'])
        self.assertTrue(form.xpath('.//details[@open]'))
        props = json.loads(tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_calendar"]/@props')[0])
        self.assertEqual(props['params'], {
            'event_type': 'game', 'team_id': str(self.team_a.id), 'show_cancelled': '1', 'search': 'lighthouse'})
        # The coach gets no « Missing timesheets » view, as on the list.
        self._login_coach()
        _text, tree = self._get('/my/events/calendar')
        self.assertNotIn('missing_timesheets', tree.xpath('//*[@data-sc-section="events.views"]//a/@data-sc-view'))
        self.assertFalse(tree.xpath('//form[@data-sc-section="events.filters"]//details[@open]'))

    # -- UC-3 ------------------------------------------------------------
    def test_list_to_calendar_keeps_filters_not_dates(self):
        self._login_tp()
        # Default list: its « from today » date is not forwarded.
        _text, tree = self._get('/my/events?team_id=%s&event_type=game&view_type=my&assigned_user_id=%s'
                                % (self.team_a.id, self.tp.id))
        url = self._segment(tree, 'calendar')
        self.assertTrue(url.startswith('/my/events/calendar?'), url)
        self.assertEqual(self._query(url), {
            'team_id': str(self.team_a.id), 'event_type': 'game', 'view_type': 'my',
            'assigned_user_id': str(self.tp.id)})
        # Explicit dates, sort, grouping and the past segment stay on the list.
        _text, tree = self._get(
            '/my/events?segment=past&no_default_dates=1&sortby=date_desc&date_to=2026-01-01'
            '&date_from=2025-01-01&group_by=team&organization_id=%s&show_cancelled=1' % self.org.id)
        self.assertEqual(self._query(self._segment(tree, 'calendar')), {
            'organization_id': str(self.org.id), 'show_cancelled': '1'})
        # The home's return_url travels too.
        _text, tree = self._get('/my/events?team_id=%s&return_url=%%2Fmy%%2Fhome' % self.team_a.id)
        self.assertEqual(self._query(self._segment(tree, 'calendar')), {
            'team_id': str(self.team_a.id), 'return_url': '/my/home'})

    def test_calendar_to_list_keeps_filters(self):
        self._login_tp()
        _text, tree = self._get('/my/events/calendar?team_id=%s&event_type=practice&show_cancelled=1'
                                '&date_from=2000-01-01' % self.team_a.id)
        upcoming = self._segment(tree, 'upcoming')
        self.assertTrue(upcoming.startswith('/my/events?'), upcoming)
        self.assertEqual(self._query(upcoming), {
            'team_id': str(self.team_a.id), 'event_type': 'practice', 'show_cancelled': '1'})
        past = self._query(self._segment(tree, 'past'))
        self.assertEqual(past['team_id'], str(self.team_a.id))
        self.assertEqual(past['event_type'], 'practice')
        self.assertEqual((past['segment'], past['no_default_dates'], past['sortby']), ('past', '1', 'date_desc'))
        self.assertIn('date_to', past)
        self.assertNotIn('date_from', past)
        # The list opened from there applies its own default range and the filters.
        _text, list_tree = self._get(upcoming)
        ids = {int(x) for x in list_tree.xpath('//*[@data-sc-section="events.list"]//@data-sc-event-id')}
        self.assertIn(self.ev_practice_a.id, ids)
        self.assertNotIn(self.ev_game_a.id, ids)
        self.assertEqual(list_tree.xpath('//form[@data-sc-section="events.filters"]//select[@name="team_id"]'
                                         '/option[@selected]/@value'), [str(self.team_a.id)])
        # The calendar's chips stay on the calendar and keep the other filters.
        chip = tree.xpath('//*[@data-sc-section="events.types"]//a[@data-sc-event-type="game"]/@href')[0]
        self.assertTrue(chip.startswith('/my/events/calendar?'), chip)
        self.assertEqual(self._query(chip), {
            'team_id': str(self.team_a.id), 'event_type': 'game', 'show_cancelled': '1'})
        mine = tree.xpath('//*[@data-sc-section="events.views"]//a[@data-sc-view="missing_timesheets"]/@href')[0]
        self.assertTrue(mine.startswith('/my/events/calendar?'), mine)
        self.assertNotIn('no_default_dates', self._query(mine))


@tagged('post_install', '-at_install')
class TestCalendarFiltersTourPhone1591(Calendar1591Common):
    browser_size = '390x844'

    def test_list_calendar_list_phone(self):
        self._switch(True)
        self.start_tour('/my/events?event_type=game&team_id=%s' % self.team_a.id,
                        'sc_1591_calendar_filters', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestCalendarFiltersTourLaptop1591(Calendar1591Common):
    browser_size = '1366x768'

    def test_list_calendar_list_laptop(self):
        self._switch(True)
        self.start_tour('/my/events?event_type=game&team_id=%s' % self.team_a.id,
                        'sc_1591_calendar_filters', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestCalendarFiltersI18n1591(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_calendar_filters_in_french(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr('/my/events/calendar'))
        form = tree.xpath('//form[@data-sc-section="events.filters"]')[0]
        text = ' '.join(form.text_content().split())
        for term in ('Filtres', 'Afficher les événements annulés', 'Appliquer les filtres',
                     'Toutes les organisations', 'Toutes les équipes'):
            self.assertIn(term, text)
        views = [' '.join(a.text_content().split())
                 for a in tree.xpath('//*[@data-sc-section="events.views"]//a')]
        self.assertIn('Mes événements', views)
