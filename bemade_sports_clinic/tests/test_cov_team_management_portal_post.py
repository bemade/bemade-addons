from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovTeamManagementPortalPost(PortalCovCommon):
    """POST-route sampling for the team-management portal (add / remove player)."""

    # ---- portal_add_player_submit ----


    # ---- portal_remove_player ----

    def test_remove_player_happy(self):
        self._login_tp()  # therapist staff on team_a
        resp = self.url_open(
            f'/my/team/{self.team_a.id}/player/{self.player.id}/remove',
            data={'csrf_token': self._csrf()})
        self.assertEqual(resp.status_code, 200)
        self.player.invalidate_recordset(['team_ids'])
        self.assertNotIn(self.team_a, self.player.team_ids)

    def test_remove_player_denied_for_plain_user(self):
        self._login_plain()  # staffs no team
        self.url_open(
            f'/my/team/{self.team_a.id}/player/{self.player.id}/remove',
            data={'csrf_token': self._csrf()})
        self.player.invalidate_recordset(['team_ids'])
        self.assertIn(self.team_a, self.player.team_ids,
                      "a non-staff user must not be able to remove the player")

    # ---- portal_search_player (jsonrpc) ----


    # ---- player-add variants ----


    def test_add_player_modal_links_existing(self):
        # player_b is on team_b only; link it to team_a via the modal flow.
        self._login_tp()
        resp = self.url_open(f'/my/team/{self.team_a.id}/player/add', data={
            'csrf_token': self._csrf(), 'existing_id': self.player_b.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.player_b.invalidate_recordset(['team_ids'])
        self.assertIn(self.team_a, self.player_b.team_ids)

    def test_request_player_removal_happy(self):
        self._login_coach()  # coach is staff on team_a
        resp = self.url_open(
            f'/my/team/{self.team_a.id}/player/{self.player.id}/request_removal',
            data={'csrf_token': self._csrf(), 'reason': 'Relocating'})
        self.assertEqual(resp.status_code, 200)
        self.player.invalidate_recordset(['pending_removal'])
        self.assertTrue(self.player.pending_removal)

    def test_request_player_removal_requires_reason(self):
        self._login_coach()
        self.url_open(
            f'/my/team/{self.team_a.id}/player/{self.player.id}/request_removal',
            data={'csrf_token': self._csrf()})
        self.player.invalidate_recordset(['pending_removal'])
        self.assertFalse(self.player.pending_removal,
                         "a removal request without a reason must not be created")

    def test_request_player_add_creates_activity(self):
        self._login_coach()
        before = self.env['mail.activity'].search_count([])
        resp = self.url_open(f'/my/team/{self.team_a.id}/player/request_add', data={
            'csrf_token': self._csrf(),
            'first_name': 'Requested', 'last_name': 'Player',
            'date_of_birth': '2007-07-07', 'reason': 'New recruit',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.env['mail.activity'].search_count([]), before + 1,
                         "the add request should create a review activity")
