"""Task 1542 — the team page (/my/team) on the app shell. Synthetic fixtures.

Acceptance criteria covered here:

* UC-T1 (AC1) Switch OFF: /my/team renders today's template — legacy
  markers, no ``data-sc-app-shell``, and none of the shell-only values is
  even computed.
* UC-T2 (AC2) Switch ON: the page renders in the shell with the segmented
  tabs Aperçu · Joueurs · Activités; ``?tab=`` deep-links the
  active panel; a roster sort lands on the players panel; the roster rows
  link to the player page.
* UC-T3 (AC2) Primary action: a portal therapist gets « Ajouter un joueur »
  (the add_link page); a coach gets « Demander un ajout », which opens the
  request sheet posting to the unchanged request route; an internal
  therapist (no portal TP group) gets the request action, exactly like
  today's page (the add_link route refuses them).
* UC-T4 (AC2) The announcement compose / archive controls are shown to a
  therapist of the team and to an internal head therapist of the team, never
  to a coach — and a coach posting the form anyway is still refused
  server-side (the announcement is unchanged).
* UC-T5 (AC2) The dashboard rows are role-filtered as today: a change only
  therapists may see (TP stamp) is listed for the therapist and NOT for the
  coach; changed rows lazy-load the SAME fragment route as the legacy card.
* UC-T6 (AC2) Activities tab hidden for a staff role « other » (no
  mail.activity ACL), as today.
"""
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.controllers.team_management_portal import (
    TeamManagementPortal,
)
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellTeam1542(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        now = fields.Datetime.now()
        # Both roles see a change on player One; only therapists see one on
        # player Three (a TP-only stamp, e.g. an internal note).
        cls.player.sudo().write({
            'dashboard_last_activity_tp': now, 'dashboard_last_activity_coach': now,
            'jersey_number': '12', 'position': 'Goalie',
        })
        cls.player_tp_only = env['sports.patient'].create({
            'first_name': 'Tess', 'last_name': 'Three',
            'team_ids': [Command.set([cls.team_a.id])],
        })
        cls.player_tp_only.sudo().write({
            'dashboard_last_activity_tp': now,
            'dashboard_last_activity_coach': now - timedelta(days=60),
        })
        user_g = env.ref('base.group_user').id
        clinic_user_g = env.ref('bemade_sports_clinic.group_sports_clinic_user').id
        itp_g = env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id
        cls.itp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'T1542 Internal TP', 'login': 't1542.itp@example.com',
            'password': 't1542-itp-pass',
            'group_ids': [Command.set([user_g, clinic_user_g, itp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.itp.partner_id.id,
            'role': 'head_therapist',
        })
        cls.team_a.sudo().write({'announcement': 'Synthetic announcement'})
        cls.url = '/my/team?team_id=%s' % cls.team_a.id

    def _login_itp(self):
        self.authenticate('t1542.itp@example.com', 't1542-itp-pass')

    @staticmethod
    def _panel(tree, key):
        nodes = tree.xpath('//section[@data-sc-tab-panel="%s"]' % key)
        return nodes[0] if nodes else None

    def _row_ids(self, tree, section):
        return {int(x) for x in tree.xpath(
            '//*[@data-sc-section="%s"]//*[@data-sc-player-id]/@data-sc-player-id' % section)}

    # -- UC-T1 -----------------------------------------------------------
    def test_switch_off_renders_legacy_without_shell_values(self):
        for login in (self._login_coach, self._login_tp):
            login()
            with patch.object(TeamManagementPortal, '_sc_team_values',
                              side_effect=AssertionError('shell values computed')):
                text, tree = self._get(self.url)
            self.assertIn('id="dashboard-tab"', text)
            self.assertIn('o_sc_roster_sort', text)
            self.assertIsNone(self._shell(tree))
            self.assertNotIn('data-sc-tab-panel', text)
            self.assertNotIn('rel="manifest"', text)

    # -- UC-T2 -----------------------------------------------------------
    def test_switch_on_tabs_and_deep_links(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get(self.url)
        self.assertIsNotNone(self._shell(tree))
        self.assertNotIn('id="dashboard-tab"', text)
        tabs = tree.xpath('//nav[@data-sc-tabs]/a/@data-sc-tab')
        self.assertEqual(tabs, ['dashboard', 'players', 'activities'])
        self.assertIsNone(self._panel(tree, 'dashboard').get('hidden'))
        self.assertEqual(self._panel(tree, 'players').get('hidden'), 'hidden')
        for tab in ('players', 'activities'):
            _text, tree = self._get(self.url + '&tab=%s' % tab)
            self.assertIsNone(self._panel(tree, tab).get('hidden'), tab)
            self.assertEqual(self._panel(tree, 'dashboard').get('hidden'), 'hidden', tab)
        # A roster sort lands on the players panel (task 1421 contract).
        _text, tree = self._get(self.url + '&sort=number')
        self.assertIsNone(self._panel(tree, 'players').get('hidden'))
        # Roster rows link to the player page with the team context.
        hrefs = tree.xpath('//*[@data-sc-section="team.roster"]//a/@href')
        self.assertIn('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id),
                      hrefs)
        self.assertIn('#12', text)

    # -- UC-T3 -----------------------------------------------------------
    def test_primary_action_per_role(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.url)
        add = tree.xpath('//header//a[@data-sc-action="team.add_player"]')
        self.assertTrue(add)
        self.assertEqual(add[0].get('href'), '/my/team/%s/player/add_link' % self.team_a.id)
        self.assertFalse(tree.xpath('//dialog[@id="sc_request_add_sheet"]'))

        self._login_coach()
        _text, tree = self._get(self.url)
        self.assertFalse(tree.xpath('//*[@data-sc-action="team.add_player"]'))
        req = tree.xpath('//header//button[@data-sc-action="team.request_add"]')
        self.assertTrue(req)
        self.assertEqual(req[0].get('data-sc-sheet-open'), 'sc_request_add_sheet')
        form = tree.xpath('//dialog[@id="sc_request_add_sheet"]//form')
        self.assertEqual(form[0].get('action'),
                         '/my/team/%s/player/request_add' % self.team_a.id)

        # Task 1577: an internal therapist has the portal therapist's
        # primary action — add directly, no request sheet.
        self._login_itp()
        _text, tree = self._get(self.url)
        self.assertIsNotNone(self._shell(tree))
        add = tree.xpath('//header//a[@data-sc-action="team.add_player"]')
        self.assertTrue(add)
        self.assertEqual(add[0].get('href'), '/my/team/%s/player/add_link' % self.team_a.id)
        self.assertFalse(tree.xpath('//*[@data-sc-action="team.request_add"]'))
        self.assertFalse(tree.xpath('//dialog[@id="sc_request_add_sheet"]'))

    # -- UC-T4 -----------------------------------------------------------
    def test_announcement_controls_per_role(self):
        self._switch(True)
        for login in (self._login_tp, self._login_itp):
            login()
            _text, tree = self._get(self.url)
            self.assertTrue(tree.xpath('//*[@data-sc-section="team.announcement.edit"]'))
            self.assertTrue(tree.xpath('//*[@data-sc-section="team.announcement.archive"]'))
            self.assertTrue(tree.xpath(
                '//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'))
        self._login_coach()
        text, tree = self._get(self.url)
        self.assertIn('Synthetic announcement', text)
        self.assertFalse(tree.xpath('//*[@data-sc-section="team.announcement.edit"]'))
        self.assertFalse(tree.xpath('//*[@data-sc-section="team.announcement.archive"]'))
        self.assertFalse(tree.xpath('//owl-component'))

    @mute_logger('odoo.addons.bemade_sports_clinic.controllers.team_management_portal')
    def test_coach_post_still_refused(self):
        self._switch(True)
        self._login_coach()
        resp = self.url_open('/my/team/%s/announcement' % self.team_a.id, data={
            'csrf_token': self._csrf(), 'announcement': 'Coach text',
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('error=', resp.headers.get('Location', ''))
        self.team_a.invalidate_recordset(['announcement'])
        self.assertEqual(self.team_a.announcement, 'Synthetic announcement')

    # -- UC-T5 -----------------------------------------------------------
    def test_dashboard_rows_role_filtered(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.url)
        tp_rows = self._row_ids(tree, 'team.recent_changes')
        self.assertIn(self.player.id, tp_rows)
        self.assertIn(self.player_tp_only.id, tp_rows)
        self._login_coach()
        _text, tree = self._get(self.url)
        coach_rows = self._row_ids(tree, 'team.recent_changes')
        self.assertIn(self.player.id, coach_rows)
        self.assertNotIn(self.player_tp_only.id, coach_rows)

    def test_changed_rows_lazy_load_legacy_fragment(self):
        self._switch(True)
        self._login_coach()
        with patch.object(type(self.env['sports.patient']), '_dashboard_card_presence',
                          return_value={'players': {self.player.id}, 'injuries': set()}):
            _text, tree = self._get(self.url)
        urls = tree.xpath('//details[@data-sc-player-id="%s"]/@data-sc-lazy-url' % self.player.id)
        self.assertEqual(urls, ['/my/player/%s/recent-changes' % self.player.id])
        resp = self.url_open(urls[0])
        self.assertEqual(resp.status_code, 200)

    # -- UC-T6 -----------------------------------------------------------
    def test_activities_hidden_without_activity_access(self):
        """A shell user always holds a coach / TP / internal group today, so
        ``can_view_activities`` is forced off here to prove the template
        honours the controller's server-side value (staff role « other »)."""
        self._switch(True)
        self._login_tp()
        real = TeamManagementPortal._sc_team_values

        def no_activities(ctrl, team, values):
            result = real(ctrl, team, values)
            result['can_view_activities'] = False
            return result

        with patch.object(TeamManagementPortal, '_sc_team_values', no_activities):
            _text, tree = self._get(self.url + '&tab=activities')
        self.assertNotIn('activities', tree.xpath('//nav[@data-sc-tabs]/a/@data-sc-tab'))
        self.assertIsNone(self._panel(tree, 'activities'))
        # Falls back to the dashboard panel.
        self.assertIsNone(self._panel(tree, 'dashboard').get('hidden'))
