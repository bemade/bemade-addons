from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovTaskManagementPortal(PortalCovCommon):
    """GET-route coverage for the task/activity portal controller."""

    def test_view_activities(self):
        self._login_tp()
        self.assertEqual(self.url_open('/my/activities').status_code, 200)

    def test_view_player_activities(self):
        self._login_tp()
        resp = self.url_open(f'/my/player/activities?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)

    def test_view_team_activities(self):
        self._login_tp()
        resp = self.url_open(f'/my/team/activities?team_id={self.team_a.id}')
        self.assertEqual(resp.status_code, 200)

    def test_view_injury_activities_redirects_to_player_tab(self):
        # Task 1409: the per-injury activities page is retired; old links land
        # on the player page's Activities tab.
        self._login_tp()
        resp = self.url_open(
            f'/my/injury/activities?injury_id={self.injury.id}', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        location = resp.headers.get('Location', '')
        self.assertIn(f'/my/player?player_id={self.player.id}', location)
        self.assertIn('#activities', location)

    def test_view_injury_activities_forbidden_for_unrelated(self):
        # Plain portal user staffs no team -> denial must be a real 403, not a 200 page.
        self._login_plain()
        resp = self.url_open(f'/my/injury/activities?injury_id={self.injury.id}')
        self.assertEqual(resp.status_code, 403)

    def test_view_event_activities(self):
        self._login_tp()
        resp = self.url_open(f'/my/event/activities?event_id={self.event.id}')
        self.assertEqual(resp.status_code, 200)

    def test_create_activity_form(self):
        self._login_tp()
        resp = self.url_open(f'/my/activity/create?model=sports.patient&res_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)

    def test_view_activity_detail(self):
        self._login_tp()
        self.assertEqual(self.url_open(f'/my/activity/{self.act_player.id}').status_code, 200)

    def test_edit_activity_form(self):
        self._login_tp()
        self.assertEqual(self.url_open(f'/my/activity/{self.act_player.id}/edit').status_code, 200)

    def test_view_messages(self):
        self._login_tp()
        resp = self.url_open(f'/my/messages?model=sports.patient&res_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)

    def test_view_attachments(self):
        self._login_tp()
        resp = self.url_open(f'/my/attachments?model=sports.patient&res_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
