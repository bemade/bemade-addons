"""Task 1742 — « Feuilles de temps manquantes » counts an event once it has
STARTED (owner 2026-11-02). Synthetic fixtures only (this repository is
public).

Cause: the shared predicate (sports.event._sc_missing_timesheet_domain) had
no time bound; the dashboard added « started », but the events list
(/my/events?view_type=missing_timesheets) defaulted ``date_to`` to the
server's UTC date — every later event of today, and tomorrow's after 20:00
in Québec.

Acceptance criteria:

* UC-1 The shared predicate keeps only started events: an event later today
  is not missing, one that started is.
* UC-2 Québec evenings / nights (freeze time, tz America/Toronto): at 20:30
  tomorrow's event and tonight's 21:00 one are absent, tonight's 19:00 one is
  present — in the predicate and in the events list; at 00:30 the 00:15 one
  is present, the 08:00 one absent.
* UC-3 The dashboard widget and its « See all » list show the same events
  (the list link carries the widget's lower bound, ``date_from``).
"""
from datetime import datetime, timedelta

from freezegun import freeze_time
from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common

LIST = '/my/events?view_type=missing_timesheets&assigned_user_id=%s&no_default_dates=1'


@tagged('post_install', '-at_install')
class TestMissingTimesheetsStarted1742(Dashboard1624Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tp.sudo().tz = 'America/Toronto'

    def _event(self, name, start):
        return self.env['sports.event'].create({
            'name': name, 'event_type': 'game', 'state': 'confirmed',
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'team_ids': [Command.set(self.team_a.ids)],
            'assigned_staff_ids': [Command.set(self.tp.ids)],
        })

    def _missing(self):
        Event = self.env['sports.event'].with_user(self.tp)
        return Event.search(Event._sc_missing_timesheet_domain(self.tp))

    def _list_ids(self, url=None):
        _text, tree = self._get(url or LIST % self.tp.id)
        return {int(i) for i in tree.xpath('//*[@data-sc-event-id]/@data-sc-event-id')}

    # -- UC-1 ---------------------------------------------------------------
    def test_started_only(self):
        now = fields.Datetime.now()
        later = self._event('SC1742 Later today', now + timedelta(hours=2))
        started = self._event('SC1742 Started', now - timedelta(hours=1))
        missing = self._missing()
        self.assertIn(started, missing)
        self.assertNotIn(later, missing)
        self._login_tp()
        ids = self._list_ids()
        self.assertIn(started.id, ids)
        self.assertNotIn(later.id, ids)

    # -- UC-2 ---------------------------------------------------------------
    def test_quebec_evening(self):
        # 2026-11-10 20:30 in Québec (EST) = 2026-11-11 01:30 UTC.
        tonight_19 = self._event('SC1742 Tonight 19h', datetime(2026, 11, 11, 0, 0))
        tonight_21 = self._event('SC1742 Tonight 21h', datetime(2026, 11, 11, 2, 0))
        tomorrow = self._event('SC1742 Tomorrow 10h', datetime(2026, 11, 11, 15, 0))
        with freeze_time('2026-11-11 01:30:00'):
            missing = self._missing()
            self.assertIn(tonight_19, missing)
            self.assertNotIn(tonight_21, missing)
            self.assertNotIn(tomorrow, missing)
            self._login_tp()
            ids = self._list_ids()
        self.assertIn(tonight_19.id, ids)
        self.assertNotIn(tonight_21.id, ids)
        self.assertNotIn(tomorrow.id, ids)

    def test_quebec_night(self):
        # 2026-11-11 00:30 in Québec = 05:30 UTC.
        early = self._event('SC1742 00h15', datetime(2026, 11, 11, 5, 15))
        morning = self._event('SC1742 08h00', datetime(2026, 11, 11, 13, 0))
        with freeze_time('2026-11-11 05:30:00'):
            missing = self._missing()
        self.assertIn(early, missing)
        self.assertNotIn(morning, missing)

    # -- UC-3 ---------------------------------------------------------------
    def test_widget_equals_list(self):
        now = fields.Datetime.now()
        self._event('SC1742 Later today', now + timedelta(hours=2))
        self._event('SC1742 Started', now - timedelta(hours=1))
        self._event('SC1742 Long ago', now - timedelta(days=45))
        self._login_tp()
        _text, tree = self._get('/my/home')
        section = self._section(tree, 'missing_timesheets')
        widget = {int(i) for i in section.xpath('.//*[@data-sc-event-id]/@data-sc-event-id')}
        self.assertTrue(widget)
        link = section.xpath('.//a[contains(@href, "view_type=missing_timesheets")]/@href')[0]
        self.assertIn('date_from=', link)
        self.assertEqual(self._list_ids(link.replace('&amp;', '&')), widget)
