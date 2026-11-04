"""Task 1618 — laptop: the back arrow next to the breadcrumb on every
sub-page (owner review 2026-10-18 reversed the « only when it adds
something » rule; static/tests/tours/sc_back_arrow_1618_tours.js,
static/src/js/sc_app_nav.js). Synthetic fixtures only.

Acceptance criteria:

* UC-B1 (laptop) Normal drill-down — team page → one of its players: the
  breadcrumb AND the back arrow; the arrow returns to the team page.
* UC-B2 (laptop) Sideways arrival — activities list (filtered) → an activity
  whose parent is the player: the back arrow shows next to the breadcrumb and
  returns to the activities list we came from, its filter kept.
* UC-B3 (laptop) Installed app (``display-mode: standalone``, emulated with a
  matchMedia stub) and a plain browser tab: the back arrow shows next to the
  trail, even on a deep link (then it goes to the parent).
* UC-B4 (phone) Unchanged: the back chevron after a drill-down, no trail.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_nav_1579 import Nav1579Common


class _Tours1618(Nav1579Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.activity = env['mail.activity'].create({
            'res_model_id': env['ir.model']._get('sports.patient').id,
            'res_id': cls.player.id,
            'activity_type_id': env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Synthetic 1618 follow-up',
            'user_id': cls.tp.id,
            'date_deadline': fields.Date.today() + timedelta(days=1),
        })

    def setUp(self):
        super().setUp()
        self.players_url = '/my/team?team_id=%s&tab=players' % self.team_a.id
        self.player_team_url = '/my/player?player_id=%s&team_id=%s' % (
            self.player.id, self.team_a.id)


@tagged('post_install', '-at_install')
class TestBackArrowLaptop1618(_Tours1618):
    browser_size = '1366x768'

    def test_drill_down_shows_the_arrow_too(self):
        self.start_tour(self.players_url, 'sc_1618_laptop_drill_down', login='pc.tp@example.com')

    def test_sideways_arrival_shows_the_arrow(self):
        self.start_tour('/my/activities?sc_clock=1', 'sc_1618_laptop_sideways',
                        login='pc.tp@example.com')

    def test_installed_app_shows_the_arrow(self):
        self.start_tour(self.player_team_url, 'sc_1618_laptop_standalone',
                        login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestBackArrowPhone1618(_Tours1618):
    browser_size = '390x844'

    def test_phone_unchanged(self):
        self.start_tour(self.players_url, 'sc_1618_phone_unchanged', login='pc.tp@example.com')
