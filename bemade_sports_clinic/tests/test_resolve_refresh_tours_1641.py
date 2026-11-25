"""Task 1641 — the injury card's « Résoudre » button refreshes the card
(static/tests/tours/sc_resolve_refresh_1641_tours.js). Synthetic fixtures
only.

Acceptance criteria covered here:

* AC-1 Phone (390 px) and laptop (1366 px): « Resolve » on an injury
  card's row — the focus where a tap leaves it: on the button (Chrome
  desktop / Android) or on the card's <summary> (WebKit: Safari and Chrome
  on iPhone, the owner's device) — then the
  sheet's confirm: the card's status pill reads « resolved » and its
  « Resolve » button is gone, without a reload. On a collapsed row and on
  an open card (task 1616: the former injury page).
* AC-2 The injury is resolved in the database. The player keeps another
  active injury, so no #1603 proposal sheet opens (its focus move hid the
  bug).

A real phone tap-through stays UNVERIFIED until /dev-review.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_injury_quick_tours_1604 import QuickToursCommon


class ResolveRefreshCommon(QuickToursCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A second ACTIVE injury: resolving the ankle is not the player's
        # last one, so no #1603 proposal sheet opens (its focus move would
        # hide the bug — the owner's case).
        cls.wrist = cls.env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic wrist'})
        cls.wrist.with_context(mail_notrack=True).write({'stage': 'active'})


class ResolveRefreshTours:

    def _player_url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id

    def _row(self, focus):
        self.start_tour(self._player_url(), 'sc_1641_resolve_row_%s' % focus,
                        login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.injury.stage, 'resolved')

    def _open_card(self, focus):
        self.start_tour('%s&injury=%s' % (self._player_url(), self.injury.id),
                        'sc_1641_resolve_open_card_%s' % focus, login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.injury.stage, 'resolved')

    def test_resolve_row_button_focused(self):
        self._row('button')

    def test_resolve_row_summary_focused(self):
        self._row('summary')

    def test_resolve_open_card_button_focused(self):
        self._open_card('button')

    def test_resolve_open_card_summary_focused(self):
        self._open_card('summary')


@tagged('post_install', '-at_install')
class TestResolveRefreshPhone1641(ResolveRefreshTours, ResolveRefreshCommon):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestResolveRefreshLaptop1641(ResolveRefreshTours, ResolveRefreshCommon):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
