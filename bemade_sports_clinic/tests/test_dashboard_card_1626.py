"""Task 1626 — the team dashboard's « Recent changes » cards work like the
other player cards (« Other players to watch », the roster, /my/players).
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 Every « Recent changes » card on the team dashboard is a player row
  (sc_player_row): its face always carries the main link to the player page
  (the right arrow), the ⚡ « Recent changes » pill, the « Removal pending »
  chip when set, and a « Details » toggle — no native <details> card left.
* UC-2 The card's « Details » region lazy-loads the player's change detail
  (/my/player/<id>/recent-changes?detail=1), not the plain row detail; ids
  stay unique when the player is also listed in another section.
* UC-3 The change detail ends with « Open the player page » (the link moved
  from the old <details> body into the fragment); the legacy portal card's
  fragment (no ``detail``) does not gain it.
* UC-4 The training recommendation icon is a heartbeat everywhere: the row
  line, the change detail, and no view of the module still uses the
  graduation cap (cards, digest history / email, legacy portal pages).
* UC-5 (tour, phone width) on any card type, while « Details » is open the
  face's training and « Retour prévu » lines are hidden (the detail has
  them); collapsing shows them again. A recent-changes card's « Details »
  loads the change detail under the row, without leaving the page.
* UC-6 French (fr_CA): the change detail's « Ouvrir la fiche du joueur »
  and the card's « Détails » render translated.
"""
from datetime import date
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _text(node):
    return ' '.join(node.text_content().split())


class Dashboard1626Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        cls.player.sudo().write({
            'dashboard_last_activity_tp': now, 'dashboard_last_activity_coach': now,
            'match_status': 'no', 'practice_status': 'no',
            'training_recommendation': 'Synthetic bike only\nSecond line of advice',
            'predicted_return_date': date(2030, 1, 15),
            'last_consultation_date': date(2026, 1, 10),
        })
        cls.url = '/my/team?team_id=%s' % cls.team_a.id

    def _presence(self):
        return patch.object(
            type(self.env['sports.patient']), '_dashboard_card_presence',
            return_value={'players': {self.player.id}, 'injuries': set()})

    def _dashboard_row(self, tree):
        rows = tree.xpath('//*[@data-sc-section="team.recent_changes"]'
                          '//*[contains(@class, "o_sc_player_row")][@data-sc-player-id="%s"]'
                          % self.player.id)
        self.assertEqual(len(rows), 1)
        return rows[0]


@tagged('post_install', '-at_install')
class TestDashboardCard1626(Dashboard1626Common):

    # -- UC-1 ------------------------------------------------------------
    def test_recent_change_card_is_a_player_row(self):
        self._switch(True)
        for login in (self._login_tp, self._login_coach):
            login()
            with self._presence():
                _t, tree = self._get(self.url)
            section = tree.xpath('//*[@data-sc-section="team.recent_changes"]')[0]
            self.assertFalse(section.xpath('.//details'), 'a native <details> card is left')
            row = self._dashboard_row(tree)
            main = row.xpath('.//a[contains(@class, "o_sc_link_row_main")]')
            self.assertEqual(len(main), 1)
            self.assertEqual(main[0].get('href'), '/my/player?player_id=%s&team_id=%s'
                             % (self.player.id, self.team_a.id))
            # No <a> inside an <a>.
            self.assertFalse(row.xpath('.//a//a'))
            pill = row.xpath('.//*[contains(@class, "o_sc_recent_pill")]')
            self.assertEqual(len(pill), 1)
            self.assertTrue(row.xpath('.//*[@data-sc-row-training]'))
            self.assertTrue(row.xpath('.//*[@data-sc-row-return]'))
            self.assertEqual(len(row.xpath('.//button[@data-sc-row-expand]')), 1)

    def test_recent_change_card_removal_pending(self):
        self.player.sudo().write({'pending_removal': True})
        self._switch(True)
        self._login_tp()
        with self._presence():
            _t, tree = self._get(self.url)
        self.assertIn('Removal pending', _text(self._dashboard_row(tree)))

    # -- UC-2 ------------------------------------------------------------
    def test_details_region_loads_change_detail(self):
        self._switch(True)
        self._login_coach()
        with self._presence():
            _t, tree = self._get(self.url)
        row = self._dashboard_row(tree)
        button = row.xpath('.//button[@data-sc-row-expand]')[0]
        region = row.xpath('.//*[@data-sc-row-detail]')
        self.assertEqual(len(region), 1)
        self.assertEqual(region[0].get('id'), button.get('data-sc-row-expand'))
        self.assertEqual(region[0].get('hidden'), 'hidden')
        self.assertEqual(region[0].get('data-sc-lazy-url'),
                         '/my/player/%s/recent-changes?detail=1&team_id=%s'
                         % (self.player.id, self.team_a.id))
        resp = self.url_open(region[0].get('data-sc-lazy-url'))
        self.assertEqual(resp.status_code, 200)

    def test_detail_ids_unique_when_also_watched(self):
        self.team_a.sudo().dashboard_watchlist_patient_ids = [fields.Command.link(self.player.id)]
        self._switch(True)
        self._login_tp()
        with self._presence():
            _t, tree = self._get(self.url)
        ids = tree.xpath('//*[@data-sc-row-detail]/@id')
        self.assertEqual(len(ids), len(set(ids)), ids)

    # -- UC-3 ------------------------------------------------------------
    def test_change_detail_ends_with_player_link(self):
        self._switch(True)
        self._login_tp()
        base = '/my/player/%s/recent-changes?detail=1' % self.player.id
        for url, href in (
            (base + '&team_id=%s' % self.team_a.id,
             '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)),
            (base, '/my/player?player_id=%s' % self.player.id),
        ):
            _t, tree = self._get(url)
            body = tree.xpath('//*[contains(@class, "o_sc_change_detail")]')[0]
            links = body.xpath('.//a[contains(@class, "o_sc_section_more")]')
            self.assertTrue(links, url)
            last = links[-1]
            self.assertEqual(_text(last), 'Open the player page')
            self.assertEqual(last.get('href'), href)
            # Last thing in the detail.
            self.assertIs(body.xpath('./*')[-1], last)

    def test_legacy_fragment_has_no_player_link(self):
        self._switch(True)
        self._login_tp()
        text, _tree = self._get('/my/player/%s/recent-changes' % self.player.id)
        self.assertNotIn('Open the player page', text)

    # -- UC-4 ------------------------------------------------------------
    def test_training_icon_is_heartbeat(self):
        self._switch(True)
        self._login_tp()
        with self._presence():
            _t, tree = self._get(self.url)
        line = self._dashboard_row(tree).xpath('.//*[@data-sc-row-training]')[0]
        self.assertTrue(line.xpath('.//i[contains(@class, "fa-heartbeat")]'))
        self.assertFalse(line.xpath('.//i[contains(@class, "fa-graduation-cap")]'))
        text, _tree = self._get('/my/player/%s/recent-changes?detail=1' % self.player.id)
        self.assertIn('fa-heartbeat', text)
        self.assertNotIn('fa-graduation-cap', text)

    def test_no_view_uses_graduation_cap(self):
        views = self.env['ir.ui.view'].sudo().search([
            ('id', 'in', self.env['ir.model.data'].sudo().search([
                ('module', '=', 'bemade_sports_clinic'), ('model', '=', 'ir.ui.view'),
            ]).mapped('res_id')),
        ])
        offenders = [v.key or v.name for v in views
                     if 'fa-graduation-cap' in (v.with_context(lang='en_US').arch_db or '')]
        self.assertFalse(offenders)


@tagged('post_install', '-at_install')
class TestDashboardCardTour1626(Dashboard1626Common):
    browser_size = '390x844'

    def test_face_lines_hide_while_open(self):
        self._switch(True)
        with self._presence():
            self.start_tour(self.url, 'sc_1626_card_details',
                            login='pc.coach@example.com')


@tagged('post_install', '-at_install')
class TestDashboardCardI18n1626(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_card_and_detail_in_french(self):
        now = fields.Datetime.now()
        self.player.sudo().write({
            'dashboard_last_activity_tp': now, 'dashboard_last_activity_coach': now,
            'training_recommendation': 'Synthetic bike only',
        })
        self._switch(True)
        self._login_tp()
        with patch.object(type(self.env['sports.patient']), '_dashboard_card_presence',
                          return_value={'players': {self.player.id}, 'injuries': set()}):
            tree = lxml_html.fromstring(self._fr('/my/team?team_id=%s' % self.team_a.id))
        row = tree.xpath('//*[@data-sc-section="team.recent_changes"]'
                         '//*[contains(@class, "o_sc_player_row")][@data-sc-player-id="%s"]'
                         % self.player.id)[0]
        self.assertEqual(_text(row.xpath('.//button[@data-sc-row-expand]')[0]), 'Détails')
        text = self._fr('/my/player/%s/recent-changes?detail=1' % self.player.id)
        self.assertIn('Ouvrir la fiche du joueur', text)
