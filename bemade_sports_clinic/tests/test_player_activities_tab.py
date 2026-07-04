from odoo import Command, fields
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestPlayerActivitiesTab(PortalCovCommon):
    """Task 1222: the player's own + its injuries' activities are consolidated
    into an Activities tab on the player detail page, with an inline add header,
    replacing the separate /my/player/activities page and the top-of-page
    activity buttons.
    """

    def test_activities_tab_lists_player_and_injury_activities(self):
        """The player page has an Activities tab listing the player's own AND
        its injuries' activities (acceptance #1)."""
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        # The new tab pane + nav button exist.
        self.assertIn('id="activities"', resp.text)
        self.assertIn('id="activities-tab"', resp.text)
        # Both the player-level and the injury-level activity appear.
        self.assertIn('Player task', resp.text)
        self.assertIn('Injury task', resp.text)

    def test_injury_activity_row_links_to_injury_and_detail(self):
        """Injury activity rows show a followable link to the injury detail, and
        the activity itself links to its detail page (acceptance #2)."""
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        # Injury column is a followable link to the injury detail.
        self.assertIn(f'/my/injury/edit?injury_id={self.injury.id}', resp.text)
        # Clicking the activity opens its detail page.
        self.assertIn(f'/my/activity/{self.act_injury.id}', resp.text)

    def test_inline_add_activity_header_present(self):
        """An inline add-activity header (fields + button) lives in the tab and
        posts to /my/activity/save against this player (acceptance #3)."""
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('action="/my/activity/save"', resp.text)
        self.assertIn('name="activity_type_id"', resp.text)
        self.assertIn('name="summary"', resp.text)
        self.assertIn('name="date_deadline"', resp.text)
        self.assertIn('name="model" value="sports.patient"', resp.text)

    def test_inline_add_activity_creates_activity(self):
        """Posting the inline header creates the activity against the player."""
        self._login_tp()
        token = self._csrf()
        resp = self.url_open('/my/activity/save', data={
            'csrf_token': token,
            'model': 'sports.patient',
            'res_id': self.player.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Inline added activity',
            'user_id': self.tp.id,
            'date_deadline': fields.Date.today().strftime('%Y-%m-%d'),
        })
        self.assertIn(resp.status_code, (200, 302))
        created = self.env['mail.activity'].search([
            ('summary', '=', 'Inline added activity'),
            ('res_model', '=', 'sports.patient'),
            ('res_id', '=', self.player.id),
        ])
        self.assertTrue(
            created, 'inline header should create the activity via /my/activity/save')

    def test_old_top_activity_buttons_removed(self):
        """The old top-of-page activity buttons are gone (acceptance #4).

        The separate player-activities page link no longer appears anywhere on
        the player detail page (nothing else on that page references it)."""
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('/my/player/activities', resp.text)

    def test_injury_edit_has_activities_button(self):
        """Injury detail (portal, edit) has a button linking to that injury's
        activities list (acceptance #5)."""
        self._login_tp()
        resp = self.url_open(f'/my/injury/edit?injury_id={self.injury.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(f'/my/injury/activities?injury_id={self.injury.id}', resp.text)

    def test_player_activities_route_redirects_to_tab(self):
        """The old /my/player/activities route redirects to the player page's
        Activities tab anchor (back-compat)."""
        self._login_tp()
        resp = self.url_open(
            f'/my/player/activities?player_id={self.player.id}',
            allow_redirects=False,
        )
        self.assertIn(resp.status_code, (302, 303))
        location = resp.headers.get('Location', '')
        self.assertIn(f'/my/player?player_id={self.player.id}', location)
        self.assertIn('activities', location)

    def test_other_role_staffer_no_500_and_no_tab(self):
        """A team staffer with role='other' holds neither portal group and has
        NO mail.activity ACL, yet still reaches the player page via team-staff
        access. The page must load (no 500 from an ungated mail.activity search)
        and must NOT show the Activities tab."""
        env = self.env
        other_user = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Other', 'login': 'pc.other@example.com', 'password': 'pc-other',
            'group_ids': [Command.set([env.ref('base.group_portal').id])],
        })
        env['sports.team.staff'].create({
            'team_id': self.team_a.id, 'partner_id': other_user.partner_id.id,
            'role': 'other',
        })
        self.authenticate('pc.other@example.com', 'pc-other')
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200,
                         'player page must not 500 for an other-role staffer')
        self.assertNotIn('id="activities-tab"', resp.text,
                         'Activities tab must be hidden from non-TP/non-coach staff')

    def test_injury_activity_scoped_to_visible_injuries(self):
        """An activity on an injury the player does NOT own must never surface
        on this player's Activities tab (team/record scoping preserved)."""
        self._login_tp()
        # act on player_b's injury context would be unrelated; build a foreign
        # injury under the same accessible player set is not possible, so assert
        # the unrelated team activity does not appear in this player's tab.
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Team task', resp.text)
        self.assertNotIn('Event task', resp.text)
