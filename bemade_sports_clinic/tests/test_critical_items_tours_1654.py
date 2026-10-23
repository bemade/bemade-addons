"""Task 1654 — the life-threatening items in a browser
(static/tests/tours/sc_critical_items_1654_tours.js), phone 390 px and
laptop 1366 px. Synthetic fixtures only.

* TOUR-1 A therapist adds « Arachides » with EpiPen in the Allergies popup:
  the family turns « Urgent » in place (level field, list, red pill naming
  the item, EpiPen icon); removing it -> « Not urgent ». No reload.

The look (the list's spacing, the add form at phone width) stays
UNVERIFIED here — the dev-review click-through covers it.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


class _Tours1654:

    def test_therapist_adds_and_removes(self):
        self.player.sudo().write({'allergy_level': 'minor', 'allergy_epipen': False,
                                  'allergy_details': 'Synthetic kiwi', 'medical_alert_level': False})
        url = '/my/player?player_id=%s&team_id=%s&tab=injuries' % (self.player.id, self.team_a.id)
        self.start_tour(url, 'sc_1654_critical_tp', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.allergy_level, self.player.allergy_epipen), ('minor', False))
        self.assertFalse(self.player.sudo().critical_item_ids)


@tagged('post_install', '-at_install')
class TestCriticalItemsToursLaptop1654(_Tours1654, PlayerInlineCommon):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestCriticalItemsToursPhone1654(_Tours1654, PlayerInlineCommon):
    browser_size = '390x844'
    allow_inherited_tests_method = True
