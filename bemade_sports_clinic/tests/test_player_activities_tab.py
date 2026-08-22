from odoo import Command, fields
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestPlayerActivitiesTab(PortalCovCommon):
    """Task 1222: the player's activities are consolidated into an Activities
    tab on the player detail page, with an inline add header, replacing the
    separate /my/player/activities page and the top-of-page activity buttons.

    Task 1409: activities live on the PATIENT only — the former injury-level
    rows were moved to the player with a « [Injury: <diagnosis>] » summary
    prefix; the per-injury Activities button/page and the injury badge on the
    activity card are gone.
    """

    def test_activities_tab_lists_player_activities_incl_injury_prefixed(self):
        """The player page has an Activities tab listing the player's
        activities, including the ones about an injury (patient-scoped,
        injury_id link, prefixed summary) (acceptance #1 / 1409 AC1)."""
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        # The new tab pane + nav button exist.
        self.assertIn('id="activities"', resp.text)
        self.assertIn('id="activities-tab"', resp.text)
        # Both the plain player activity and the injury-prefixed one appear.
        self.assertIn('Player task', resp.text)
        self.assertIn('[Injury: Sprain] Injury task', resp.text)

    def test_injury_prefixed_activity_links_to_detail_without_injury_badge(self):
        """The activity about an injury links to its detail page like any
        other; there is no injury badge / per-injury activities link any
        more (task 1409)."""
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        # Clicking the activity opens its detail page.
        self.assertIn(f'/my/activity/{self.act_injury.id}', resp.text)
        # No injury badge on the activity card, no per-injury activities page.
        self.assertNotIn('badge text-bg-info me-1">Injury', resp.text)
        self.assertNotIn('/my/injury/activities', resp.text)

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

    def test_injury_edit_has_no_activities_button(self):
        """Injury detail (portal, edit) no longer links to a per-injury
        activities list (task 1409 — activities live on the player)."""
        self._login_tp()
        resp = self.url_open(f'/my/injury/edit?injury_id={self.injury.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('/my/injury/activities', resp.text)
        self.assertNotIn('/my/activity/create?model=sports.patient.injury', resp.text)

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

    def test_activities_tab_scoped_to_this_player(self):
        """Activities of other records (team, event, another player) must never
        surface on this player's Activities tab (record scoping preserved)."""
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Team task', resp.text)
        self.assertNotIn('Event task', resp.text)
