"""Task 1630 — the medical pills in a browser
(static/tests/tours/sc_medical_alerts_1630_tours.js), phone 390 px and
laptop 1366 px. Synthetic fixtures only.

* TOUR-TP A therapist opens the Allergies pill's popup, edits through its
  pencil (level -> urgent, EpiPen ticked); the popup and the header pill
  (red, EpiPen icon) follow in place, without a reload.
* TOUR-COACH A coach sees only the red Medical alert pill and its details,
  with no pencil and no grey / outline pill.

The look (tones in both themes, the EpiPen icon, phone popups as bottom
sheets) stays UNVERIFIED here — the dev-review click-through covers it.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


class _Tours1630:

    def _url(self):
        return '/my/player?player_id=%s&team_id=%s&tab=injuries' % (self.player.id, self.team_a.id)

    def test_therapist_edits_in_popup(self):
        self.player.sudo().write({'allergy_level': 'minor', 'allergy_epipen': False,
                                  'allergy_details': 'Synthetic kiwi', 'medical_alert_level': False})
        self.start_tour(self._url(), 'sc_1630_medical_tp', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.allergy_level, 'urgent')
        self.assertTrue(self.player.allergy_epipen)

    def test_coach_sees_red_only(self):
        self.player.sudo().write({'allergy_level': 'none', 'medical_alert_level': 'urgent',
                                  'medical_alert_details': 'Synthetic asthma'})
        self.start_tour(self._url(), 'sc_1630_medical_coach', login='pc.coach@example.com')


@tagged('post_install', '-at_install')
class TestMedicalAlertsToursLaptop1630(_Tours1630, PlayerInlineCommon):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestMedicalAlertsToursPhone1630(_Tours1630, PlayerInlineCommon):
    browser_size = '390x844'
    allow_inherited_tests_method = True
