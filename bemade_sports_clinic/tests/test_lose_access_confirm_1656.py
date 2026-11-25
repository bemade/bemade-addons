"""Task 1656 — removing the team that gives a therapist access to a player:
confirm first, then leave the page cleanly (no 403). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 The Teams field carries ``confirmRemove`` (the viewer's staffed teams
  + the popup texts) for a therapist; the widget asks only when the LAST of
  them would go (a player on A + B, viewer staffing A only: removing A asks;
  after adding another of the viewer's teams, it does not — the #1594 teams
  tour); a clinic admin gets none.
* UC-2 Saving the removal of A → ``lost_access: true`` with the « <player>
  removed from <team> » message and NO refresh patterns; the write is done.
  Removing B (access kept) answers normally; an admin's removal answers
  normally.
* UC-3 (tour, laptop) from the team page to the player: removing A opens the
  popup; « Cancel » keeps the tag and saves nothing; « Remove and leave »
  lands back on the team page with the toast — no 403.
"""
import json

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class LoseAccess1656Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.team_ids = [Command.set([cls.team_a.id, cls.team_b.id])]

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _teams_props(self, tree):
        for raw in tree.xpath('//owl-component/@props'):
            props = json.loads(raw)
            if props.get('field') == 'sc_team_ids':
                return props
        return None

    def _save_teams(self, value):
        self.player.invalidate_recordset()
        return self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'sc_team_ids', 'value': value, 'leaving': '1',
            'write_date': fields.Datetime.to_string(self.player.sudo().write_date),
            'csrf_token': self._csrf()}, allow_redirects=False)


@tagged('post_install', '-at_install')
class TestLoseAccessConfirm1656(LoseAccess1656Common):

    def test_confirm_flags(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=info' % self.player.id)
        props = self._teams_props(tree)
        rule = props.get('confirmRemove') or {}
        # The widget asks when the LAST of the viewer's teams would go (A).
        self.assertEqual(rule.get('access'), [str(self.team_a.id)])
        self.assertEqual(rule.get('confirm'), 'Remove and leave')
        self.assertIn('%s', rule.get('title'))
        self._login_cadmin()
        _text, tree = self._get('/my/player?player_id=%s&tab=info' % self.player.id)
        self.assertFalse((self._teams_props(tree) or {}).get('confirmRemove'))

    def test_removing_the_access_team_answers_lost_access(self):
        self._login_tp()
        resp = self._save_teams('')
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertTrue(payload.get('lost_access'))
        self.assertFalse(payload.get('refresh'))
        self.assertIn('removed from PC Team A', payload['message'])
        self.assertEqual(self.player.sudo().team_ids, self.team_b)

    def test_admin_removal_is_normal(self):
        self._login_cadmin()
        resp = self._save_teams(str(self.team_b.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse(resp.json().get('lost_access'))
        self.assertEqual(self.player.sudo().team_ids, self.team_b)


@tagged('post_install', '-at_install')
class TestLoseAccessConfirmTour1656(LoseAccess1656Common):
    browser_size = '1366x768'

    def test_confirm_then_leave(self):
        self.start_tour('/my/team?team_id=%s&tab=players' % self.team_a.id, 'sc_1656_lose_access',
                        login='pc.tp@example.com')
        self.assertEqual(self.player.sudo().team_ids, self.team_b)
