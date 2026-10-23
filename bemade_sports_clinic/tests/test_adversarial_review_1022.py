"""Adversarial review fixes 2026-10-22 (the #1638 → #1654 stack, 19.0.1.107.1).
Synthetic fixtures only.

Acceptance criteria:

* AR-A1 A « None known » undo never overwrites a later change: once the
  family is written again — by another therapist (edit, then clear again)
  or by the same user through add-item → remove-item — every pending
  snapshot of that player + family is gone, for every user, and the undo is
  refused (the toast's « can no longer be undone »).
* AR-A2 Undoing the clear of a legacy « Urgent » that has no item brings
  back « Urgent » (never « Not urgent »), its details and EpiPen.
* AR-S1 A portal therapist can't move a critical item of their own player
  onto another team's player, nor to the other family (AccessError); the
  other player stays untouched.
* AR-S2 The player-add existence check gives a therapist the SAME answer
  whatever date of birth is typed for a player they can't open (never
  filtered, never « exact »; an identical name only shows the generic
  « ask a manager » line). In their own teams the date still refines and
  flags the twin. At least 2 letters per name part before any search.
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
from odoo.addons.bemade_sports_clinic.tests.test_review_fixes_1022 import MedicalUndoCommon


class _UndoCommon(MedicalUndoCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'AR TP Two', 'login': 'ar1022.tp2@example.com', 'password': 'ar-1022-tp2',
            'group_ids': [Command.set([
                env.ref('base.group_portal').id,
                env.ref('bemade_sports_clinic.group_portal_treatment_professional').id])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id, 'role': 'therapist'})

    def _undos(self):
        return self.env['sports.patient.medical.undo'].sudo().search_count(
            [('patient_id', '=', self.player.id)])


@tagged('post_install', '-at_install')
class TestAdversarialUndo1022(_UndoCommon):

    # -- AR-A1 -------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_other_user_edit_then_clear_drops_the_undo(self):
        self._login_tp()
        undo = self._save_level('allergy_level', 'none').json()['undo']
        self.assertEqual(self._undos(), 1)
        # Another therapist writes the family, then clears it again.
        player = self.player.with_user(self.tp2)
        player.write({'allergy_level': 'minor', 'allergy_details': 'Synthetic pollen by TP2'})
        self.assertEqual(self._undos(), 0, 'a later change drops every pending snapshot')
        player.write({'allergy_level': 'none'})
        resp = self._post(undo['url'], token=undo['token'])
        self.assertEqual(resp.status_code, 403)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.allergy_level, self.player.allergy_details), ('none', False),
                         "TP2's clear is never overwritten by TP1's stale undo")

    @mute_logger('odoo.http')
    def test_same_user_add_then_remove_item_drops_the_undo(self):
        self._login_tp()
        undo = self._save_level('allergy_level', 'none').json()['undo']
        item = self.Item.with_user(self.tp).create({
            'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic bee'})
        self.assertEqual(self._undos(), 0)
        item.with_user(self.tp).unlink()
        self.player.invalidate_recordset()
        self.assertEqual(self.player.allergy_level, 'none')
        resp = self._post(undo['url'], token=undo['token'])
        self.assertEqual(resp.status_code, 403)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.allergy_level, self.player.allergy_details), ('none', False))

    def test_other_family_and_other_player_keep_the_undo(self):
        self._login_tp()
        undo = self._save_level('allergy_level', 'none').json()['undo']
        self.player.with_user(self.tp2).write({'medical_alert_level': 'minor'})
        self.player_b.sudo().write({'allergy_level': 'minor', 'allergy_details': 'Synthetic other'})
        self.assertEqual(self._undos(), 1)
        self.assertEqual(self._post(undo['url'], token=undo['token']).status_code, 200)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.allergy_level, self.player.allergy_details), ('minor', 'Synthetic kiwi'))

    # -- AR-A2 -------------------------------------------------------------
    def test_legacy_urgent_without_items_comes_back_urgent(self):
        self.player.sudo().write({'allergy_level': 'urgent', 'allergy_epipen': True,
                                  'allergy_details': 'Synthetic legacy bee'})
        self.assertFalse(self._items())
        self._login_tp()
        undo = self._save_level('allergy_level', 'none').json()['undo']
        resp = self._post(undo['url'], token=undo['token'])
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.player.invalidate_recordset()
        self.assertEqual((self.player.allergy_level, self.player.allergy_details, self.player.allergy_epipen),
                         ('urgent', 'Synthetic legacy bee', True))
        self.assertIn('PC TP', self.player.allergy_updated_info)
        self.assertFalse(self._items())


@tagged('post_install', '-at_install')
class TestAdversarialAccess1022(_UndoCommon):

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
    def test_out_of_team_answer_does_not_depend_on_dob(self):
        self._login_tp()
        answers = []
        for dob in ('2010-02-03', '2001-01-01', ''):
            resp, tree = self._check(first='Élodie', last='Synthé-Côté', dob=dob)
            self.assertEqual(resp.status_code, 200)
            answers.append(resp.text)
            self.assertIn(self.elodie.id, self._rows(tree), dob)
            self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['0'], dob)
            self.assertFalse(tree.xpath('//li[@data-sc-check-exact]'), dob)
            flag = tree.xpath('//*[@data-sc-check-twin-elsewhere]')
            self.assertEqual([' '.join(f.text_content().split()) for f in flag],
                             ['A player with this identity already exists — ask a manager.'], dob)
        self.assertEqual(answers[0], answers[1], 'the right and a wrong date give the same answer')
        self.assertEqual(answers[0], answers[2])
        # A prefix only (not the same name): no generic line either way.
        for dob in ('2010-02-03', '2001-01-01'):
            _resp, tree = self._check(first='elo', last='synthe', dob=dob)
            self.assertIn(self.elodie.id, self._rows(tree))
            self.assertFalse(tree.xpath('//*[@data-sc-check-twin-elsewhere]'))

    def test_in_team_dob_still_refines_and_flags(self):
        self._login_tp()
        _resp, tree = self._check(first='Pat', last='One', dob='2009-04-05')
        self.assertEqual(tree.xpath('//*[@data-sc-check-results]/@data-sc-exact'), ['1'])
        self.assertTrue(tree.xpath('//li[@data-sc-check-player="%s"][@data-sc-check-exact]' % self.player.id))
        self.assertFalse(tree.xpath('//*[@data-sc-check-twin-elsewhere]'))
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
