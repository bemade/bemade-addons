"""Task 1579 — the back / breadcrumb engine in a browser
(static/tests/tours/sc_app_nav_tours.js). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-T1 (phone) Back returns to the in-app page you came from: from a
  FILTERED players list, the player page's back lands on that filtered list
  (history), although its href is the declared parent (/my/players).
* UC-T2 (phone) A deep link falls back to the declared parent: a player
  opened from a team (team_id) goes back to the team's players tab.
* UC-T3 (phone) Team page → digest list → snapshot: back steps up one level
  each time; a snapshot opened directly (deep link) steps up the declared
  chain snapshot → list → team page, never down again.
* UC-T4 (laptop) The full trail shows (``<nav aria-label>``, ``<ol>``, the
  current page with ``aria-current``), the back chevron and context line do
  not; a crumb goes up.
* Phone pages show the back chevron + context, never the trail (checked in
  every phone tour).
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_nav_1579 import Nav1579Common


class _Tours1579(Nav1579Common):

    def setUp(self):
        super().setUp()
        self.digest_url = '/my/team/%s/digest/%s' % (self.team_a.id, self.digest.id)
        self.player_team_url = '/my/player?player_id=%s&team_id=%s' % (
            self.player.id, self.team_a.id)


@tagged('post_install', '-at_install')
class TestAppShellToursPhone1579(_Tours1579):
    browser_size = '390x844'

    def test_back_came_from(self):
        self.start_tour('/my/players?first_name=Pat', 'sc_1579_back_came_from',
                        login='pc.tp@example.com')

    def test_deep_link_fallback(self):
        self.start_tour(self.player_team_url, 'sc_1579_deep_link_fallback',
                        login='pc.tp@example.com')

    def test_digest_chain(self):
        self.start_tour(self.team_url, 'sc_1579_digest_chain', login='pc.tp@example.com')

    def test_digest_deep_link(self):
        self.start_tour(self.digest_url, 'sc_1579_digest_deep_link', login='pc.coach@example.com')


@tagged('post_install', '-at_install')
class TestAppShellToursLaptop1579(_Tours1579):
    browser_size = '1366x768'

    def test_laptop_trail(self):
        self.start_tour(self.player_team_url, 'sc_1579_laptop_trail', login='pc.tp@example.com')
