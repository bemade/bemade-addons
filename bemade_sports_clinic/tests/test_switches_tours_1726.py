"""Task 1726 — UC-5: the shared switch in each kind of form, in a browser
(static/tests/tours/sc_switches_1726_tours.js), phone 390 px and laptop
1366 px. Synthetic fixtures only.

* TOUR-PREF « Paramètres »: the « Terminé » buttons switch posts the
  preference on its own (sc_show_done_buttons -> True).
* TOUR-FILTER the events filter form: « Afficher les événements annulés »
  applies on change (show_cancelled=1 in the address).
* TOUR-AUTOSAVE the new injury's date « N/A » switch (OWL autosave field):
  on disables the date, off brings it back.
* TOUR-FETCH the Medical alert popup's « Aucune condition connue »: saved
  in place (medical_none_confirmed -> True), no reload.

The look (track, thumb, focus ring, dark / light) stays UNVERIFIED here — the
dev-review click-through on iPhone + laptop covers it.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_switches_1726 import Switch1726Common


class _Tours1726:

    def test_pref_switch(self):
        self.tp.sc_show_done_buttons = False
        self.start_tour('/my/app/settings', 'sc_1726_switch_pref', login='pc.tp@example.com')
        self.tp.invalidate_recordset()
        self.assertTrue(self.tp.sc_show_done_buttons)

    def test_filter_switch(self):
        self.start_tour('/my/events', 'sc_1726_switch_filter', login='pc.tp@example.com')

    def test_autosave_switch(self):
        self.start_tour('/my/patient/injury/new?patient_id=%s' % self.player.id,
                        'sc_1726_switch_autosave', login='pc.tp@example.com')

    def test_fetch_switch(self):
        set_medical(self.player, allergies=[], conditions=[], epipen=False,
                    none_allergy=False, none_condition=False)
        self.start_tour('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id),
                        'sc_1726_switch_fetch', login='pc.tp@example.com')
        player = self.player.sudo()
        player.invalidate_recordset()
        self.assertTrue(player.medical_none_confirmed)
        self.assertEqual(player.medical_alert_level, 'none')


@tagged('post_install', '-at_install')
class TestSwitchesToursLaptop1726(_Tours1726, Switch1726Common):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestSwitchesToursPhone1726(_Tours1726, Switch1726Common):
    browser_size = '390x844'
    allow_inherited_tests_method = True
