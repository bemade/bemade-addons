"""Daily digest snapshots match the app shell's recent-changes detail
(owner, 2026-10-11). Synthetic fixtures.

Acceptance criteria:

* UC-DS1 A snapshot read groups every injury change under its injury: the
  player's general list keeps only non-injury changes; active injuries come
  most recently changed first (unchanged last), each carrying its own
  changes and the « Recent change » flag; resolved injuries with changes in
  the snapshot window are frozen and shown under « Resolved injuries ».
* UC-DS2 The coach read drops hidden-from-coaches injuries (active or
  resolved), internal notes and internal change items, as before.
* UC-DS3 The rendered snapshot follows the same order as the live detail:
  last consultation, ⚡ general changes, « Active injuries », « Resolved
  injuries ».
* UC-DS4 A snapshot captured before this change (no ``resolved_injuries`` /
  ``last_change`` keys) still renders: injury changes join their active
  injury's card by ``injury_id``; a change whose injury has no card stays in
  the general list, so nothing is lost.
"""
import copy
from datetime import date

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_team_changes import (
    ChangeDetailFixture,
)
from odoo.addons.bemade_sports_clinic.tests.portal_cov_common import PortalCovCommon


@tagged('post_install', '-at_install')
class TestDigestSnapshotGrouping(ChangeDetailFixture, PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_change_fixture()
        cls.p.with_context(mail_notrack=True).write(
            {'last_consultation_date': date(2026, 1, 10)})
        cls.digest = cls.env['sports.team.digest']._capture_team(
            cls.team_a, fields.Datetime.now(), fields.Date.today(), 'UTC')

    def _player(self, role, digest=None):
        players = (digest or self.digest)._render_for_role(role)
        return next(p for p in players if p['player_id'] == self.p.id)

    @staticmethod
    def _names(injuries):
        return [(i['diagnosis'], len(i.get('items') or []), bool(i.get('changed')))
                for i in injuries]

    # -- UC-DS1 ----------------------------------------------------------
    def test_tp_read_groups_changes_by_injury(self):
        player = self._player('tp')
        self.assertEqual([it['field'] for it in player['items']], ['match_status'])
        self.assertEqual(self._names(player['active_injuries']), [
            ('Synthetic ankle', 1, True), ('Synthetic knee', 1, True),
            ('Synthetic wrist', 0, False)])
        self.assertEqual(sorted(self._names(player['resolved_injuries'])), [
            ('Synthetic hip', 1, True), ('Synthetic shoulder', 2, True)])

    # -- UC-DS2 ----------------------------------------------------------
    def test_coach_read_drops_hidden_and_internal(self):
        player = self._player('coach')
        names = [i['diagnosis'] for i in player['active_injuries'] + player['resolved_injuries']]
        self.assertNotIn('Synthetic hip', names)
        shoulder = next(i for i in player['resolved_injuries']
                        if i['diagnosis'] == 'Synthetic shoulder')
        self.assertEqual(shoulder['internal_notes'], '')
        self.assertEqual([it['field'] for it in shoulder['items']], ['stage'])

    # -- UC-DS3 ----------------------------------------------------------
    def test_rendered_order(self):
        body = self.env['ir.qweb']._render('bemade_sports_clinic.team_digest_render', {
            'players': [self._player('tp')], 'announcement': None})
        tree = lxml_html.fromstring(str(body))
        text = ' '.join(tree.text_content().split()).lower()
        text = text[text.index('hide details'):]  # the header pill says it too
        order = ['last consultation', 'recent changes', 'active injuries', 'synthetic ankle',
                 'synthetic knee', 'synthetic wrist', 'resolved injuries', 'synthetic shoulder']
        positions = [text.find(t) for t in order]
        self.assertNotIn(-1, positions, text)
        self.assertEqual(positions, sorted(positions), text)
        cards = tree.xpath('//*[contains(@class, "o_sc_injury_detail")]')
        ankle = next(c for c in cards if 'Synthetic ankle' in c.text_content())
        self.assertTrue(ankle.xpath('.//*[contains(@class, "o_sc_injury_changed")]'))
        self.assertTrue(ankle.xpath('.//*[contains(@class, "dashboard-digest-item")]'))
        general = tree.xpath('//*[contains(@class, "o_sc_recent_changes_content")]'
                             '/*[contains(@class, "dashboard-digest")]'
                             '//*[contains(@class, "dashboard-digest-item")]')
        self.assertEqual(len(general), 1)

    # -- UC-DS4 ----------------------------------------------------------
    def test_old_snapshot_without_new_keys(self):
        data = copy.deepcopy(self.digest.item_data)
        for player in data['players']:
            player.pop('resolved_injuries', None)
            for inj in player.get('active_injuries', []):
                inj.pop('last_change', None)
        old = self.env['sports.team.digest'].create({
            'team_id': self.team_b.id, 'snapshot_date': fields.Date.today(),
            'captured_at': fields.Datetime.now(), 'timezone': 'UTC', 'item_data': data,
        })
        player = self._player('tp', old)
        self.assertEqual(player['resolved_injuries'], [])
        ankle = next(i for i in player['active_injuries'] if i['diagnosis'] == 'Synthetic ankle')
        self.assertEqual(len(ankle['items']), 1)
        general = {(it['field'], it.get('injury_diagnosis')) for it in player['items']}
        self.assertIn(('match_status', False), general)
        self.assertIn(('stage', 'Synthetic shoulder'), general)
