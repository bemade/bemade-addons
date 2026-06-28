from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovTimesheetsPortal(PortalCovCommon):
    """GET-route coverage for the timesheets portal controller."""

    def test_view_timesheets(self):
        self._login_tp()
        self.assertEqual(self.url_open('/my/sc/timesheets').status_code, 200)

    def test_view_timesheets_filtered(self):
        self._login_tp()
        url = ('/my/sc/timesheets?date_from=2026-01-01&date_to=2026-12-31'
               f'&team_id={self.team_a.id}&group_by=event&sortby=date')
        self.assertEqual(self.url_open(url).status_code, 200)

    def test_cancelled_event_timesheet_excluded(self):
        """A timesheet on a cancelled event drops out of both the portal
        list and the 'My Timesheets' home counter (task 990)."""
        now = datetime(2026, 3, 3, 10, 0)
        cancelled_event = self.env['sports.event'].create({
            'name': 'PC Cancelled Event', 'event_type': 'game',
            'team_ids': [Command.set([self.team_a.id])],
            'date_start': now, 'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([self.tp.id])],
        })
        self.env['sports.event.timesheet'].create({
            'event_id': cancelled_event.id, 'user_id': self.tp.id,
        })
        cancelled_event.state = 'cancelled'

        self._login_tp()

        # List route: keeps the confirmed-event timesheet, drops the cancelled one.
        resp = self.url_open('/my/sc/timesheets')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('PC Event', resp.text)
        self.assertNotIn('PC Cancelled Event', resp.text)

        # Home counter: the async /my/counters route excludes it too. Baseline
        # is the single confirmed-event timesheet created in PortalCovCommon.
        counters = self._jsonrpc('/my/counters', counters=['event_timesheets_count'])
        self.assertEqual(counters['event_timesheets_count'], 1)
