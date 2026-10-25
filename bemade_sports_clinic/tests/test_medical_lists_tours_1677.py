"""Task 1677 — the structured allergy / condition lists in a browser
(static/tests/tours/sc_medical_lists_1677_tours.js), phone 390 px and
laptop 1366 px. Synthetic fixtures only.

* TOUR-1 A therapist: the Allergies popup's EpiPen card (tick, note, ✓),
  « + Ajouter » an allergy, « Risque vital » -> red live (popup and header
  pill), the trash can -> yellow again; no reload.
* TOUR-2 A therapist: the Medical alert popup (grey) — a life-threatening
  condition with its first-aid note -> red, the card shows the first aid.

The look (cards, spacing, phone bottom sheet) stays UNVERIFIED here — the
dev-review click-through covers it.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


class _Tours1677:

    def _url(self):
        return '/my/player?player_id=%s&team_id=%s&tab=injuries' % (self.player.id, self.team_a.id)

    def test_allergies_tour(self):
        set_medical(self.player, allergies=[('Synthetic kiwi', False)], conditions=[], epipen=False,
                    none_allergy=False, none_condition=False)
        self.start_tour(self._url(), 'sc_1677_allergies_tp', login='pc.tp@example.com')
        player = self.player.sudo()
        player.invalidate_recordset()
        self.assertEqual([(i.name, i.life_threatening) for i in player.allergy_critical_ids],
                         [('Synthetic kiwi', False)])
        self.assertEqual((player.allergy_level, player.allergy_epipen, player.allergy_epipen_note),
                         ('minor', True, 'Sac, poche avant'))

    def test_conditions_tour(self):
        set_medical(self.player, allergies=[('Synthetic kiwi', False)], conditions=[],
                    none_allergy=False, none_condition=False)
        self.start_tour(self._url(), 'sc_1677_conditions_tp', login='pc.tp@example.com')
        player = self.player.sudo()
        player.invalidate_recordset()
        self.assertEqual([(i.name, i.life_threatening, i.first_aid_note) for i in player.medical_alert_critical_ids],
                         [('Asthme', True, 'Ventolin, 2 inhalations')])
        self.assertEqual(player.medical_alert_level, 'urgent')


@tagged('post_install', '-at_install')
class TestMedicalListsToursLaptop1677(_Tours1677, PlayerInlineCommon):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestMedicalListsToursPhone1677(_Tours1677, PlayerInlineCommon):
    browser_size = '390x844'
    allow_inherited_tests_method = True
