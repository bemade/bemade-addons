from datetime import datetime

from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovEventsPortal(PortalCovCommon):
    """GET-route coverage for the events portal controller."""

    def test_view_events_list(self):
        self._login_tp()
        self.assertEqual(self.url_open('/my/events').status_code, 200)

    def test_cancelled_event_hidden_then_shown(self):
        """Portal events list hides cancelled events by default (task 1235)
        and surfaces them again with show_cancelled=1."""
        self._login_tp()
        self.env['sports.event'].create({
            'name': 'PC Cancelled Zebra',
            'event_type': 'game',
            'team_ids': [Command.set([self.team_a.id])],
            'date_start': datetime(2026, 2, 3, 10, 0),
            'date_end': datetime(2026, 2, 3, 12, 0),
            'state': 'cancelled',
            'assigned_staff_ids': [Command.set([self.tp.id])],
        })
        # no_default_dates avoids the today-onward default date filter that
        # would otherwise hide these Feb-2026 fixtures regardless of state.
        resp = self.url_open('/my/events?no_default_dates=1')
        self.assertIn(b'PC Event', resp.content)              # confirmed shows
        self.assertNotIn(b'PC Cancelled Zebra', resp.content)  # cancelled hidden

        resp = self.url_open('/my/events?no_default_dates=1&show_cancelled=1')
        self.assertIn(b'PC Cancelled Zebra', resp.content)     # toggle reveals it

    def test_view_events_filtered(self):
        self._login_tp()
        url = (f'/my/events?view_type=my&team_id={self.team_a.id}'
               f'&organization_id={self.org.id}&search=PC&date_from=2026-01-01&date_to=2026-12-31')
        self.assertEqual(self.url_open(url).status_code, 200)

    def test_view_events_unassigned_filter(self):
        self._login_tp()
        self.assertEqual(self.url_open('/my/events?view_type=unassigned').status_code, 200)

    def test_view_event_detail(self):
        self._login_tp()
        self.assertEqual(self.url_open(f'/my/event/{self.event.id}').status_code, 200)

    def test_edit_event_form(self):
        self._login_tp()
        self.assertEqual(self.url_open(f'/my/event/{self.event.id}/edit').status_code, 200)

    def test_create_event_form(self):
        self._login_tp()
        self.assertEqual(self.url_open('/my/event/create').status_code, 200)

    def test_view_calendar(self):
        self._login_coach()
        self.assertEqual(self.url_open('/my/events/calendar').status_code, 200)

    def test_calendar_data(self):
        self._login_coach()
        resp = self.url_open('/my/events/calendar/data?start=2026-01-01T00:00:00&end=2026-12-31T00:00:00')
        self.assertEqual(resp.status_code, 200)
