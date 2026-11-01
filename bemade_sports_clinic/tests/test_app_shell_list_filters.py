"""Events and Timesheets in the app shell get back every filter the legacy
portal had (owner review 2026-10-11). Synthetic fixtures only.

Acceptance criteria:

* UC-LF1 Events: the views « All », « My events », « Unassigned » and (for
  therapists) « Missing timesheets »; a filter panel with organization,
  team, assigned professional, from / to dates, « Show cancelled », sort and
  group by — keeping the segment (upcoming / past) and the event type.
* UC-LF2 Events filters apply (a team narrows the list; « Show cancelled »
  brings cancelled events back) and « Group by » renders one titled group
  per team / month / week / therapist.
* UC-LF3 Timesheets: the filter panel adds organization, sort and group by
  to search, dates and team; « Group by » renders titled groups.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellListFilters(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start = fields.Datetime.now() + timedelta(days=3)
        Event = cls.env['sports.event']
        cls.ev_a = Event.create({
            'name': 'Synthetic A game', 'event_type': 'game', 'team_ids': [Command.set([cls.team_a.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2)})
        cls.ev_b = Event.create({
            'name': 'Synthetic B game', 'event_type': 'game', 'team_ids': [Command.set([cls.team_b.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2)})
        cls.ev_cancel = Event.create({
            'name': 'Synthetic cancelled', 'event_type': 'game', 'team_ids': [Command.set([cls.team_a.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2)})
        cls.ev_cancel.write({'state': 'cancelled'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _event_ids(tree):
        return {int(x) for x in tree.xpath('//*[@data-sc-section="events.list"]//*[@data-sc-event-id]/@data-sc-event-id')}

    # -- UC-LF1 ----------------------------------------------------------
    def test_events_views_and_filter_panel(self):
        self._login_tp()
        _text, tree = self._get('/my/events?event_type=game')
        views = tree.xpath('//*[@data-sc-section="events.views"]//a/@data-sc-view')
        self.assertEqual(views, ['all', 'my', 'unassigned', 'missing_timesheets'])
        form = tree.xpath('//form[@data-sc-section="events.filters"]')[0]
        names = set(form.xpath('.//*[@name]/@name'))
        # Task 1607 (deliberate update): the sort is in the list header (the
        # form carries it as a hidden field once chosen).
        for name in ('organization_id', 'team_id', 'assigned_user_id', 'date_from', 'date_to',
                     'show_cancelled', 'group_by', 'event_type', 'view_type'):
            self.assertIn(name, names)
        self.assertTrue(tree.xpath('//*[@data-sc-section="events.sort"]//a[@data-sc-sort="date_desc"]'))
        self.assertEqual(form.xpath('.//input[@name="event_type"]/@value'), ['game'])
        self._login_coach()
        _text, tree = self._get('/my/events')
        views = tree.xpath('//*[@data-sc-section="events.views"]//a/@data-sc-view')
        self.assertNotIn('missing_timesheets', views)

    # -- UC-LF2 ----------------------------------------------------------
    def test_events_filters_apply_and_group(self):
        self._login_tp()
        _text, tree = self._get('/my/events?team_id=%s' % self.team_a.id)
        ids = self._event_ids(tree)
        self.assertIn(self.ev_a.id, ids)
        self.assertNotIn(self.ev_b.id, ids)
        self.assertNotIn(self.ev_cancel.id, ids)
        _text, tree = self._get('/my/events?team_id=%s&show_cancelled=1' % self.team_a.id)
        self.assertIn(self.ev_cancel.id, self._event_ids(tree))
        _text, tree = self._get('/my/events?group_by=team')
        groups = tree.xpath('//*[@data-sc-section="events.list"]//*[@data-sc-group]')
        titles = [' '.join(g.xpath('.//*[contains(@class, "o_sc_group_title")]')[0].text_content().split())
                  for g in groups]
        # The therapist staffs Team A only (Team B's events are out of scope).
        self.assertTrue(any(self.team_a.name in t for t in titles), titles)
        team_a = next(g for g in groups if self.team_a.name in g.text_content())
        self.assertIn(str(self.ev_a.id), team_a.xpath('.//*[@data-sc-event-id]/@data-sc-event-id'))

    # -- UC-LF3 ----------------------------------------------------------
    def test_timesheets_filters_and_group(self):
        self._login_tp()
        _text, tree = self._get('/my/sc/timesheets')
        form = tree.xpath('//form[@data-sc-section="timesheets.filters"]')[0]
        names = set(form.xpath('.//*[@name]/@name'))
        for name in ('search', 'date_from', 'date_to', 'team_id', 'organization_id', 'group_by'):
            self.assertIn(name, names)
        self.assertTrue(tree.xpath('//*[@data-sc-section="timesheets.sort"]//a[@data-sc-sort="state"]'))
        _text, tree = self._get('/my/sc/timesheets?group_by=team&no_default_dates=1&date_from=2000-01-01')
        groups = tree.xpath('//*[@data-sc-section="timesheets.list"]//*[@data-sc-group]')
        self.assertTrue(groups)
