"""Task 1539 — browser tours of the P2 shell pages (static/tests/tours/
sc_app_p2_tours.js), at phone width (390 px) and on a laptop (1366 px).
Synthetic fixtures only.

Acceptance criteria covered here (AC3 / AC4 / AC6 in a browser):

* UC-T1 Players list -> player page -> tabs switched in place (?tab= kept).
* UC-T2 (AC3) Injury edit: an external note is saved when the field is left
  (EXACTLY one note-history row); « Résoudre » saves at once and « Annuler »
  in the toast re-posts the previous status.
* UC-T3 (AC4) New injury: typed -> leave -> return -> « Brouillon restauré »
  -> « Créer » -> ONE injury created, the device draft is gone; nothing was
  created before « Créer ».
* UC-T4 Activity « Fait » from the player's Activities tab through the sheet.

Visual layout, both themes, both navigation modes and the three roles side
by side stay UNVERIFIED here — the dev-review click-through covers them.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class _Tour1539Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')


@tagged('post_install', '-at_install')
class TestAppShellToursPhone1539(_Tour1539Common):
    browser_size = '390x844'

    def test_players_to_player_phone(self):
        self.start_tour('/my/players', 'sc_1539_players_to_player', login='pc.coach@example.com')

    def test_new_injury_draft_phone(self):
        Injury = self.env['sports.patient.injury']
        before = Injury.search_count([('patient_id', '=', self.player.id)])
        self.start_tour('/my/patient/injury/new?patient_id=%s' % self.player.id,
                        'sc_1539_new_injury_draft', login='pc.coach@example.com')
        created = Injury.search([('patient_id', '=', self.player.id),
                                 ('diagnosis', '=', 'Tour 1539 synthetic diagnosis')])
        self.assertEqual(len(created), 1)
        self.assertEqual(Injury.search_count([('patient_id', '=', self.player.id)]), before + 1)


@tagged('post_install', '-at_install')
class TestAppShellToursLaptop1539(_Tour1539Common):
    browser_size = '1366x768'

    def test_players_to_player_laptop(self):
        self.start_tour('/my/players', 'sc_1539_players_to_player', login='pc.tp@example.com')

    def test_injury_autosave_laptop(self):
        History = self.env['sports.injury.note.history']
        before = History.search_count([('injury_id', '=', self.injury.id),
                                       ('scope', '=', 'external')])
        self.start_tour('/my/injury/edit?injury_id=%s' % self.injury.id,
                        'sc_1539_injury_autosave', login='pc.tp@example.com')
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'Tour 1539 synthetic external note')
        self.assertEqual(History.search_count([('injury_id', '=', self.injury.id),
                                               ('scope', '=', 'external')]), before + 1)
        self.assertEqual(self.injury.stage, 'active')

    def test_activity_complete_laptop(self):
        self.start_tour('/my/player?player_id=%s&tab=activities' % self.player.id,
                        'sc_1539_activity_complete', login='pc.tp@example.com')
        self.act_player.invalidate_recordset()
        self.act_injury.invalidate_recordset()
        remaining = self.env['mail.activity'].search_count([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id)])
        self.assertEqual(remaining, 1)
