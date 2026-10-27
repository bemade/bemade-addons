"""Adversarial review fixes 2026-10-22 (the #1638 → #1654 stack, 19.0.1.107.1).
Synthetic fixtures only.

Acceptance criteria:

* (AR-A1 / AR-A2, the « None known » undo, were removed with it by task
  1677: no level is chosen any more, nothing to undo.)
* AR-S1 A portal therapist can't move a critical item of their own player
  onto another team's player, nor to the other family (AccessError); the
  other player stays untouched.
* AR-S2 (rewritten by task 1716, owner 2026-10-26: the « date-of-birth
  oracle » concern is waived) The player-add existence check treats a
  player the therapist can't open like their own: the typed date of birth
  refines the list and flags the exact twin (with its team), and no « ask a
  manager » line exists any more. At least 2 letters per name part before
  any search.
* AR-S3 A coach can't write the « Updated on … by … » stamps.
* AR-S4 The header search never lists an archived player outside the
  therapist's own teams; their own archived players stay, last and greyed.
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_header_search_1650 import Search1650Common
from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common
from odoo.addons.bemade_sports_clinic.tests.test_medical_lists_1677 import MedicalLists1677Common


@tagged('post_install', '-at_install')
class TestAdversarialAccess1022(MedicalLists1677Common):

    # -- AR-S1 -------------------------------------------------------------
    def test_item_cannot_move_to_another_player_or_family(self):
        before = (self.player_b.allergy_level, self.player_b.medical_alert_level)
        item = self.Item.with_user(self.tp).create({
            'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic planted'})
        with self.assertRaises(AccessError):
            item.write({'patient_id': self.player_b.id})
        with self.assertRaises(AccessError):
            item.write({'family': 'medical_alert'})
        self.player_b.invalidate_recordset()
        self.assertEqual((self.player_b.allergy_level, self.player_b.medical_alert_level), before)
        self.assertFalse(self.Item.sudo().search_count([('patient_id', '=', self.player_b.id)]))
        # The same values, and the other fields, still go through.
        item.write({'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic renamed'})
        self.assertEqual(item.sudo().name, 'Synthetic renamed')

    # -- AR-S3 -------------------------------------------------------------
    def test_coach_cannot_forge_the_stamp(self):
        for name in ('allergy_updated_info', 'medical_alert_updated_info'):
            with self.assertRaises(AccessError):
                self.player.with_user(self.coach).write({name: 'Updated on 2026-01-01 by Forged'})
        self.player.invalidate_recordset()
        self.assertNotIn('Forged', self.player.allergy_updated_info or '')


@tagged('post_install', '-at_install')
class TestAdversarialPlayerCheck1022(PlayerAdd1655Common):

    def _rows(self, tree):
        return [int(li.get('data-sc-check-player')) for li in tree.xpath('//li[@data-sc-check-player]')]

    # -- AR-S2 -------------------------------------------------------------
    def test_out_of_team_answer_follows_the_dob(self):
        # Task 1716: was test_out_of_team_answer_does_not_depend_on_dob (the
        # same answer whatever the date + the generic line). Now the right
        # date flags the twin, a wrong one drops the row, none lists it.
        self._login_tp()
        resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='2010-02-03')
        self.assertIn(self.elodie.id, self._rows(tree))
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['1'])
        self.assertTrue(tree.xpath('//li[@data-sc-check-player="%s"][@data-sc-check-exact]' % self.elodie.id))
        self.assertNotIn('ask a manager', resp.text)
        resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='2001-01-01')
        self.assertNotIn(self.elodie.id, self._rows(tree))
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['0'])
        resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='')
        self.assertIn(self.elodie.id, self._rows(tree))
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['0'])

    def test_in_team_dob_still_refines_and_flags(self):
        self._login_tp()
        _resp, tree = self._check(first='Pat', last='One', dob='2009-04-05')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['1'])
        self.assertTrue(tree.xpath('//li[@data-sc-check-player="%s"][@data-sc-check-exact]' % self.player.id))
        _resp, tree = self._check(first='Pat', last='One', dob='2001-01-01')
        self.assertNotIn(self.player.id, self._rows(tree))
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['0'])
        # A clinic admin opens everyone: the date refines and flags anywhere.
        self._login_cadmin()
        _resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='2010-02-03')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['1'])
        _resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob='2001-01-01')
        self.assertNotIn(self.elodie.id, self._rows(tree))

    def test_two_letters_per_name_part(self):
        self._login_tp()
        for first, last in (('p', 'one'), ('pat', 'o'), ('', 'one')):
            _resp, tree = self._check(first=first, last=last)
            self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-ready'), ['0'], (first, last))
            self.assertFalse(self._rows(tree), (first, last))
        _resp, tree = self._check(first='pa', last='on')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-ready'), ['1'])
        self.assertIn(self.player.id, self._rows(tree))


@tagged('post_install', '-at_install')
class TestAdversarialSearch1022(Search1650Common):

    # -- AR-S4 -------------------------------------------------------------
    def test_archived_out_of_team_not_listed(self):
        gone = self.env['sports.patient'].create({'first_name': 'Eloise', 'last_name': 'Synthetic-Gone'})
        gone.team_ids = [Command.set([self.team_b.id])]
        gone.active = False
        self._login_tp()
        resp = self.url_open('/my/app/search?q=synth')
        tree = lxml_html.fromstring('<div>%s</div>' % resp.text)
        ids = [int(li.get('data-sc-search-player')) for li in tree.xpath('//li[@data-sc-search-player]')]
        self.assertNotIn(gone.id, ids, 'an archived out-of-team player is never listed')
        self.assertIn(self.other.id, ids, 'active out-of-team players still are (locked)')
        self.assertEqual(ids[-1], self.old.id, 'the own archived player stays, last')
        row = self._players(tree)[self.old.id]
        self.assertIn('o_sc_search_archived', row.get('class'))
        # A clinic admin still finds it (their scope is everything).
        self.authenticate('search1650.admin@example.com', 'search-1650-admin')
        resp = self.url_open('/my/app/search?q=synth')
        tree = lxml_html.fromstring('<div>%s</div>' % resp.text)
        self.assertIn(gone.id, self._players(tree))
