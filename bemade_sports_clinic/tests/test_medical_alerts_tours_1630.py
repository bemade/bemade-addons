"""Task 1630 — the medical pills in a browser
(static/tests/tours/sc_medical_alerts_1630_tours.js), phone 390 px and
laptop 1366 px. Synthetic fixtures only.

* (TOUR-TP and TOUR-PENCIL, the level editor, were replaced by task 1677's
  structured lists: test_medical_lists_tours_1677.)
* TOUR-COACH A coach sees only the red Medical alert pill and its details,
  with no pencil and no grey / outline pill.
* TOUR-CARD (review round 1) A coach's roster card shows the compact red
  pills (EpiPen icon); no horizontal scroll at phone width. Task 1652: a
  tap on a pill opens its popup (read-only for a coach).

The look (tones in both themes, the EpiPen icon, phone popups as bottom
sheets) stays UNVERIFIED here — the dev-review click-through covers it.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


class _Tours1630:

    def _url(self):
        return '/my/player?player_id=%s&team_id=%s&tab=injuries' % (self.player.id, self.team_a.id)

    def test_coach_sees_red_only(self):
        set_medical(self.player, allergies=[], conditions=[('Synthetic asthma', True)], none_allergy=True)
        self.start_tour(self._url(), 'sc_1630_medical_coach', login='pc.coach@example.com')

    def test_card_pills_open_the_player(self):
        set_medical(self.player, allergies=[('Synthetic peanut', True)],
                    conditions=[('Synthetic epilepsy', True)], epipen=True)
        self.start_tour('/my/team?team_id=%s&tab=players' % self.team_a.id, 'sc_1630_card_pills',
                        login='pc.coach@example.com')


@tagged('post_install', '-at_install')
class TestMedicalAlertsToursLaptop1630(_Tours1630, PlayerInlineCommon):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestMedicalAlertsToursPhone1630(_Tours1630, PlayerInlineCommon):
    browser_size = '390x844'
    allow_inherited_tests_method = True
