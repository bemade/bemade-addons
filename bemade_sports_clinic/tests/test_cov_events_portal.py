from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovEventsPortal(PortalCovCommon):
    """GET-route coverage for the events portal controller."""

    def test_view_events_list(self):
        self._login_tp()
        self.assertEqual(self.url_open('/my/events').status_code, 200)

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
