"""Task 1225: the broadened /my/players search must not offer a (403-bound)
"View" link for players the current user cannot open, and must instead offer an
"Add to Team" action limited to teams the user staffs. Using it links the player
and the detail page then becomes reachable.

Personas come from PortalCovCommon: cls.tp staffs team_a only; cls.player
("Pat One") is on team_a (accessible); cls.player_b ("Pat Two") is on team_b
(out of reach for the TP).
"""
from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestPortalPlayerSearchAddToTeam(PortalCovCommon):

    # ---- search results: hide View, offer Add-to-Team for out-of-reach ----

    def test_search_hides_view_link_for_inaccessible_player(self):
        """A TP searching by name finds an out-of-team player, but the result
        carries no /my/player View link (which would 403) - it carries the
        Add-to-Team form instead."""
        self._login_tp()
        resp = self.url_open(f'/my/players?last_name=Two')
        self.assertEqual(resp.status_code, 200)
        # The out-of-team player is surfaced by the broadened search...
        self.assertIn('Two', resp.text, "the broadened search should surface the out-of-team player")
        # ...but with NO clickable View link (no 403 reachable)...
        self.assertNotIn(f'/my/player?player_id={self.player_b.id}', resp.text,
                         "no View link may point at a player the user cannot open")
        # ...and WITH an Add-to-Team action.
        self.assertIn(f'/my/player/{self.player_b.id}/add_to_team', resp.text,
                      "an Add-to-Team action must be offered for the out-of-team player")

    def test_search_keeps_view_link_for_accessible_player(self):
        """An own-team player keeps the normal View link and no Add-to-Team."""
        self._login_tp()
        resp = self.url_open(f'/my/players?last_name=One')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(f'/my/player?player_id={self.player.id}', resp.text,
                      "an accessible player must keep its View link")
        self.assertNotIn(f'/my/player/{self.player.id}/add_to_team', resp.text,
                         "an accessible player must not show Add-to-Team")

    # ---- add-to-team action ----

    def test_add_to_team_links_player_and_grants_access(self):
        """Posting Add-to-Team for a staffed team links the player and the
        detail page (previously 403) becomes reachable."""
        self._login_tp()
        # Pre-condition: TP cannot open player_b.
        pre = self.url_open(f'/my/player?player_id={self.player_b.id}')
        self.assertEqual(pre.status_code, 403)

        resp = self.url_open(f'/my/player/{self.player_b.id}/add_to_team', data={
            'csrf_token': self._csrf(), 'team_id': self.team_a.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.player_b.invalidate_recordset(['team_ids'])
        self.assertIn(self.team_a, self.player_b.team_ids,
                      "the player should be linked to the chosen staffed team")

        # The View now works.
        post = self.url_open(f'/my/player?player_id={self.player_b.id}')
        self.assertEqual(post.status_code, 200,
                         "the detail page must be reachable once the player is on a staffed team")

    def test_add_to_team_rejects_unstaffed_team(self):
        """A TP may not add a player to a team they do not staff (the posted
        team_id is never trusted)."""
        self._login_tp()
        # team_b is NOT staffed by the TP. self.player is on team_a only.
        self.url_open(f'/my/player/{self.player.id}/add_to_team', data={
            'csrf_token': self._csrf(), 'team_id': self.team_b.id,
        })
        self.player.invalidate_recordset(['team_ids'])
        self.assertNotIn(self.team_b, self.player.team_ids,
                         "the player must not be linked to a team the user does not staff")

    def test_add_to_team_denied_for_coach(self):
        """Coaches keep the request-based flow; the direct Add-to-Team link is
        TP/admin only and must not mutate the roster for a coach."""
        self._login_coach()
        self.url_open(f'/my/player/{self.player_b.id}/add_to_team', data={
            'csrf_token': self._csrf(), 'team_id': self.team_a.id,
        })
        self.player_b.invalidate_recordset(['team_ids'])
        self.assertNotIn(self.team_a, self.player_b.team_ids,
                         "a coach must not directly link a player via Add-to-Team")
