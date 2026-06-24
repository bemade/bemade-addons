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
