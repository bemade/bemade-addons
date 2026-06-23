from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovTeamManagementPortalPost(PortalCovCommon):
    """POST-route sampling for the team-management portal (add / remove player)."""

    # ---- portal_add_player_submit ----

    def test_add_player_submit_happy(self):
        self._login_tp()
        resp = self.url_open(f'/my/team/{self.team_a.id}/add_player/submit', data={
            'csrf_token': self._csrf(),
            'first_name': 'Postadd', 'last_name': 'Newplayer',
            'date_of_birth': '2005-05-05',
        })
        self.assertEqual(resp.status_code, 200)
        patient = self.env['sports.patient'].search([
            ('first_name', '=', 'Postadd'), ('last_name', '=', 'Newplayer'),
        ])
        self.assertTrue(patient, "the player should have been created")
        self.assertIn(self.team_a, patient.team_ids)

    def test_add_player_submit_invalid_dob_shows_error_not_500(self):
        # Regression: the error path re-renders portal_add_player, which calls
        # user_has_group(...) — previously a 500 because the context lacked it.
        self._login_tp()
        resp = self.url_open(f'/my/team/{self.team_a.id}/add_player/submit', data={
            'csrf_token': self._csrf(),
            'first_name': 'Bad', 'last_name': 'Date', 'date_of_birth': 'not-a-date',
        })
        self.assertEqual(resp.status_code, 200, "invalid DOB must render the form, not 500")
        self.assertIn('first_name', resp.text)  # the form was re-rendered
        self.assertFalse(self.env['sports.patient'].search([
            ('first_name', '=', 'Bad'), ('last_name', '=', 'Date')]),
            "no player should be created on a validation error")

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

    def test_portal_search_player(self):
        self._login_tp()
        result = self._jsonrpc(f'/my/team/{self.team_a.id}/player/search', first_name='Pat')
        self.assertTrue(result.get('ok'))
        self.assertTrue(result.get('active'), "the search should return matching active players")

    def test_portal_search_player_requires_name(self):
        self._login_tp()
        result = self._jsonrpc(f'/my/team/{self.team_a.id}/player/search', first_name='', last_name='')
        self.assertFalse(result.get('ok'))
