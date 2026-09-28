"""Task 1539 — players on the app shell: the players list, the player page,
player create / edit and the emergency-contact forms. Synthetic fixtures.

Acceptance criteria covered here:

* UC-P1 (AC1) Switch OFF: every P2 player URL renders today's template
  (legacy markers, no ``data-sc-app-shell``), the shell values are not even
  computed, and the e-mail deep link ``/my/player?player_id=`` keeps
  working.
* UC-P2 (AC2) Players list in the shell: entity rows linking to the player
  page; the jersey (#1421), team and status filters keep their query
  parameters; a therapist's name search across teams lists out-of-team
  players WITHOUT a link, with « Ajouter à l'équipe » posting to the
  unchanged route; « Créer un joueur » for therapists only.
"""
from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.team_staff_portal import TeamStaffPortal
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class PlayersCommon1539(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.player.sudo().write({
            'jersey_number': '12', 'position': 'Goalie', 'allergies': 'Synthetic allergy',
            'team_info_notes': 'Synthetic team note', 'date_of_birth': '2010-05-06',
            'training_recommendation': 'Bike 15 min (synthetic)',
        })
        cls.hidden_injury = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Hidden synthetic injury',
            'hidden_from_coaches': True,
        })
        cls.hidden_injury.sudo().write({
            'stage': 'active', 'internal_notes': 'Internal synthetic text'})
        cls.injury.sudo().write({'internal_notes': 'TP-only synthetic remark',
                                 'external_notes': 'Visible synthetic remark'})

    @staticmethod
    def _panel(tree, key):
        nodes = tree.xpath('//section[@data-sc-tab-panel="%s"]' % key)
        return nodes[0] if nodes else None


@tagged('post_install', '-at_install')
class TestAppShellPlayersList1539(PlayersCommon1539):

    # -- UC-P1 -----------------------------------------------------------
    def test_switch_off_players_legacy(self):
        for login in (self._login_coach, self._login_tp):
            login()
            with patch.object(TeamStaffPortal, '_sc_players_values',
                              side_effect=AssertionError('shell values computed')):
                text, tree = self._get('/my/players')
            self.assertIn('o_portal_search_panel', text)
            self.assertIsNone(self._shell(tree))
            self.assertNotIn('data-sc-app-shell', text)

    # -- UC-P2 -----------------------------------------------------------
    def test_players_rows_in_shell(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get('/my/players')
        self.assertIsNotNone(self._shell(tree))
        self.assertNotIn('o_portal_search_panel', text)
        hrefs = tree.xpath('//*[@data-sc-section="players.list"]//a/@href')
        self.assertIn('/my/player?player_id=%s' % self.player.id, hrefs)
        self.assertIn('#12', text)
        # Coach: no « Créer un joueur ».
        self.assertFalse(tree.xpath('//*[@data-sc-action="players.create"]'))
        self._login_tp()
        _text, tree = self._get('/my/players')
        action = tree.xpath('//header//a[@data-sc-action="players.create"]')
        self.assertEqual(action[0].get('href'), '/my/player/create')

    def test_filters_keep_their_params(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/players?jersey_number=%2312')
        ids = [int(x) for x in tree.xpath('//*[@data-sc-player-id]/@data-sc-player-id')]
        self.assertEqual(ids, [self.player.id])
        self.assertEqual(tree.xpath('//input[@name="jersey_number"]/@value'), ['12'])
        _text, tree = self._get('/my/players?team_id=%s&match_status=no' % self.team_a.id)
        self.assertFalse(tree.xpath('//*[@data-sc-section="players.list"]'))

    def test_name_search_out_of_team_offers_add(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/players?last_name=Two')
        locked = tree.xpath('//*[@data-sc-row-locked][@data-sc-player-id="%s"]' % self.player_b.id)
        self.assertTrue(locked)
        self.assertFalse(locked[0].xpath('.//a'))
        form = locked[0].xpath('.//form')
        self.assertEqual(form[0].get('action'), '/my/player/%s/add_to_team' % self.player_b.id)
        self.assertEqual(form[0].xpath('.//select/option/@value'), [str(self.team_a.id)])
        # A coach's name search never broadens.
        self._login_coach()
        _text, tree = self._get('/my/players?last_name=Two')
        self.assertFalse(tree.xpath('//*[@data-sc-player-id="%s"]' % self.player_b.id))

    def test_player_with_many_teams_subtitle(self):
        self.player.sudo().team_ids = [Command.link(self.team_b.id)]
        self._switch(True)
        self._login_coach()
        text, _tree = self._get('/my/players')
        self.assertIn('PC Team A, PC Team B', text)
