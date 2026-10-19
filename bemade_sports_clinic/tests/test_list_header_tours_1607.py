"""Task 1607 — the list header in a browser
(static/tests/tours/sc_list_header_1607_tours.js). Synthetic fixtures only.

Acceptance criteria covered here (UC-H6):

* Laptop (1366 px) and phone (360 px): the players list header holds
  « + Ajouter » on the left and the sort menu on the right on ONE line,
  directly above the list, without a sideways scroll, 44 px targets, nothing
  left in the app bar; the sort menu opens on the checked option, Escape
  closes it (focus back), choosing an option reloads the list sorted;
  « + Ajouter » opens the player creation.
* The team roster's « + Ajouter » opens the add-player panel right under the
  header with the focus in its first field, and closes it again.

The look in both themes and real screen readers stay UNVERIFIED here — the
dev-review click-through covers them.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class _ListHeaderTourMixin:
    """The tours, run at two widths by the tagged classes below (a plain
    mixin: Odoo's loader only runs the test methods a class defines itself
    unless allow_inherited_tests_method)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')

    def test_players(self):
        self.start_tour('/my/players', 'sc_1607_players', login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.tp.players_sort_mode, 'name')

    def test_team_add(self):
        self.start_tour('/my/team?team_id=%s&tab=players' % self.team_a.id, 'sc_1607_team_add',
                        login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestListHeaderToursLaptop1607(_ListHeaderTourMixin, AppShellCommon):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestListHeaderToursPhone1607(_ListHeaderTourMixin, AppShellCommon):
    browser_size = '360x740'
    allow_inherited_tests_method = True
