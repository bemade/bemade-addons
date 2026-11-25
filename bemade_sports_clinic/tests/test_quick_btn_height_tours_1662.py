"""Task 1662 — the injury card's quick « Vérifier » / « Résoudre » button is
the same height as the pills on its row; no overlap when the row wraps.
Synthetic fixtures only.

Acceptance criteria (static/tests/tours/sc_quick_btn_1662_tours.js), at
390 px (phone) and 1366 px (laptop), for a therapist on the player page
Blessures tab:

* AC-1 An active injury carrying the « Consentement à compléter » and
  « Masquée aux entraîneurs » chips + its status pill: the « Résoudre »
  button's height equals the status pill's (±1 px).
* AC-2 No two items of the row (quick button, chips, clock, status pill,
  chevron) intersect, and none overflows the row.
* AC-3 The same for an unverified injury (« Vérifier »).

The real iPhone rendering stays UNVERIFIED until /dev-review.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class QuickBtn1662Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # The active injury: long diagnosis + both chips (no parental
        # consent recorded, hidden from coaches).
        cls.injury.with_context(mail_notrack=True).write({
            'diagnosis': 'Synthetic long diagnosis of the left ankle ligaments',
            'hidden_from_coaches': True,
            'parental_consent': False,
        })
        cls.unverified = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic wrist strain'})
        cls.unverified.with_context(mail_notrack=True).write({'stage': 'unverified'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id


@tagged('post_install', '-at_install')
class TestQuickBtnHeightPhone1662(QuickBtn1662Common):
    browser_size = '390x844'

    def test_quick_button_matches_pills_phone(self):
        self.start_tour(self._url(), 'sc_1662_quick_btn_height', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestQuickBtnHeightLaptop1662(QuickBtn1662Common):
    browser_size = '1366x768'

    def test_quick_button_matches_pills_laptop(self):
        self.start_tour(self._url(), 'sc_1662_quick_btn_height', login='pc.tp@example.com')
