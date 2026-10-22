"""Task 1643 — the app bar and the bottom tabs stay pinned in the mobile
browser (static/tests/tours/sc_bars_pinned_1643_tours.js, phone 390 px).
Synthetic fixtures only.

Acceptance criteria covered here:

* AC-1 On a long app page (team page, player list) the WINDOW scrolls
  (document.scrollingElement, never #wrapwrap) and, scrolled by 600 px,
  the app bar's top stays at 0 and the tabs' bottom at the viewport's.
* AC-2 No ancestor of the bars scrolls or carries a transform / filter /
  contain / will-change (each breaks sticky or re-bases fixed); one
  viewport meta, with viewport-fit=cover.

* AC-3 (addendum) On a neutralized test DB the red banner is pinned at the
  bottom of a phone screen and the tabs sit right above it (never under
  it); the banner stays visible.

Run with ``website`` installed too (the project CI / a prod copy): that is
where the frontend layout's own rules apply. iPhone Chrome / Safari with a
collapsing address bar stays UNVERIFIED until /dev-review.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestBarsPinnedTours1643(AppShellCommon):
    browser_size = '390x844'

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_team_page(self):
        self.start_tour('/my/team?team_id=%s' % self.team_a.id, 'sc_1643_bars_pinned',
                        login='pc.tp@example.com')

    def test_player_list(self):
        self.start_tour('/my/players', 'sc_1643_bars_pinned', login='pc.coach@example.com')

    def test_neutralize_banner_above_tabs(self):
        self.env.ref('web.neutralize_banner').active = True
        self.start_tour('/my/players', 'sc_1643_ribbon', login='pc.coach@example.com')
