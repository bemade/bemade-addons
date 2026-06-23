from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovTeamManagementPortal(PortalCovCommon):
    """GET-route coverage for the team-management portal controller."""

    def test_portal_team_players(self):
        self._login_coach()
        resp = self.url_open(f'/my/team/{self.team_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Pat', resp.text)

    def test_portal_team_players_access_denied_redirects(self):
        # Coach does not staff team_b: _check_team_access raises, the controller
        # catches it and redirects to /my/teams (so the roster is NOT shown).
        self._login_coach()
        resp = self.url_open(f'/my/team/{self.team_b.id}')
        self.assertEqual(resp.status_code, 200)  # followed redirect
        self.assertNotIn('Two', resp.text)  # team_b player (Pat Two) must not leak

    def test_portal_add_player_form(self):
        self._login_coach()
        resp = self.url_open(f'/my/team/{self.team_a.id}/add_player')
        self.assertEqual(resp.status_code, 200)
        # Locale-independent: the add-player form posts to this action.
        self.assertIn(f'/my/team/{self.team_a.id}/add_player/submit', resp.text)

    def test_portal_add_link_player_page(self):
        self._login_coach()
        resp = self.url_open(f'/my/team/{self.team_a.id}/player/add_link')
        self.assertEqual(resp.status_code, 200)
