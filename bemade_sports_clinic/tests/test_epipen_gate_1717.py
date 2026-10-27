"""Task 1717 — EpiPen becomes the allergies gate: empty (« Not provided »,
new players) / Yes / No. Synthetic fixtures only.

Acceptance criteria:

* AC-1 Migration: every existing boolean True becomes « yes », every False
  (or NULL) « no »; no existing player stays empty; counts before = after.
* AC-2 A new player starts empty; the former boolean follows the answer
  (stored compute) and a write of the boolean answers it (inverse).
* AC-3 Gate (server): while EpiPen is empty, adding an allergy and ticking
  « No known allergy » are refused with a clear message — through the app
  routes (400 JSON) and the ORM; conditions keep their own « none known »;
  once answered, both work. Scripts (superuser) are exempt.
* AC-4 Pill: empty → the allergies pill reads « Not provided » (grey); the
  EpiPen card asks « EpiPen? » Yes / No first (open on load for a
  therapist) and the allergies' Add control waits for it.
* AC-5 To-Do: a player created by a user with EpiPen empty raises ONE
  To-Do to that creator « Complete the medical file (allergies/EpiPen) »;
  never twice; never for the superuser; done when EpiPen is answered.
* AC-6 French: « Non renseigné », « EpiPen ? », the gate message, the To-Do.
* AC-7 (review round 1, owner 2026-10-27): the answer is ONE line — the
  « EpiPen » label and a segmented Oui / Non slider pill
  (``o_sc_toggle_pill``, a radiogroup named by the label), nothing selected
  while unanswered.
"""
import importlib.util
import os

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_medical_lists_1677 import MedicalLists1677Common


def _load_migration():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'migrations', '19.0.1.123.0', 'pre-migrate.py')
    spec = importlib.util.spec_from_file_location('bsc_migration_19_0_1_123_0', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EpiPen1717Common(MedicalLists1677Common):

    def _new_player(self, user=None, **vals):
        Patient = self.env['sports.patient'].with_user(user) if user else self.env['sports.patient']
        vals = dict({'first_name': 'Epi', 'last_name': 'Synthgate', 'date_of_birth': '2011-02-03',
                     'team_ids': [Command.set([self.team_a.id])]}, **vals)
        return Patient.create_portal_patient(vals) if user else Patient.create(vals)

    def _todos(self, player):
        return self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', player.id), ('sc_epipen_todo', '=', True)])


@tagged('post_install', '-at_install')
class TestEpiPenGate1717(EpiPen1717Common):

    # -- AC-1 --------------------------------------------------------------
    def test_migration_maps_the_boolean(self):
        players = self.env['sports.patient'].create([
            {'first_name': 'Mig%s' % i, 'last_name': 'Synth', 'team_ids': [Command.set([self.team_a.id])]}
            for i in range(3)])
        players.flush_recordset()
        cr = self.env.cr
        cr.execute("UPDATE sports_patient SET allergy_epipen = TRUE, allergy_epipen_state = NULL WHERE id = %s",
                   (players[0].id,))
        cr.execute("UPDATE sports_patient SET allergy_epipen = FALSE, allergy_epipen_state = NULL WHERE id = %s",
                   (players[1].id,))
        cr.execute("UPDATE sports_patient SET allergy_epipen = NULL, allergy_epipen_state = NULL WHERE id = %s",
                   (players[2].id,))
        cr.execute("UPDATE sports_patient SET allergy_epipen_state = NULL")
        cr.execute("SELECT COUNT(*) FILTER (WHERE allergy_epipen), COUNT(*) FROM sports_patient")
        yes_before, total = cr.fetchone()
        _load_migration().migrate(cr, '19.0.1.122.0')
        cr.execute("""SELECT COUNT(*) FILTER (WHERE allergy_epipen_state = 'yes'),
                             COUNT(*) FILTER (WHERE allergy_epipen_state = 'no'),
                             COUNT(*) FILTER (WHERE allergy_epipen_state IS NULL) FROM sports_patient""")
        yes, no, empty = cr.fetchone()
        self.assertEqual((yes, no, empty), (yes_before, total - yes_before, 0))
        players.invalidate_recordset()
        self.assertEqual(players.sudo().mapped('allergy_epipen_state'), ['yes', 'no', 'no'])
        # Idempotent.
        _load_migration().migrate(cr, '19.0.1.122.0')
        players.invalidate_recordset()
        self.assertEqual(players.sudo().mapped('allergy_epipen_state'), ['yes', 'no', 'no'])

    # -- AC-2 --------------------------------------------------------------
    def test_new_player_empty_and_boolean_follows(self):
        player = self._new_player().sudo()
        self.assertFalse(player.allergy_epipen_state)
        self.assertFalse(player.allergy_epipen)
        player.write({'allergy_epipen_state': 'yes'})
        self.assertTrue(player.allergy_epipen)
        player.write({'allergy_epipen': False})
        self.assertEqual(player.allergy_epipen_state, 'no')

    # -- AC-3 --------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_gate_through_the_app(self):
        player = self._new_player()
        self._login_tp()
        resp = self._post('/my/app/medical/item/add', patient_id=player.id, family='allergy', name='Synthetic nut')
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn('EpiPen', resp.json()['message'])
        resp = self._post('/my/app/medical/%s/set' % player.id, field='allergy_none_confirmed', value='1')
        self.assertEqual(resp.status_code, 400, resp.text)
        # Conditions keep their own « none known ».
        resp = self._post('/my/app/medical/%s/set' % player.id, field='medical_none_confirmed', value='1')
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self._post('/my/app/medical/%s/set' % player.id, field='allergy_epipen_state', value='maybe')
        self.assertEqual(resp.status_code, 400, resp.text)
        resp = self._post('/my/app/medical/%s/set' % player.id, field='allergy_epipen_state', value='no')
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self._post('/my/app/medical/item/add', patient_id=player.id, family='allergy', name='Synthetic nut')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(player.sudo().allergy_epipen_state, 'no')

    def test_gate_orm(self):
        player = self._new_player()
        with self.assertRaisesRegex(ValidationError, 'EpiPen'):
            self.env['sports.patient.critical.item'].with_user(self.tp).create({
                'patient_id': player.id, 'family': 'allergy', 'name': 'Synthetic nut'})
        with self.assertRaisesRegex(ValidationError, 'EpiPen'):
            player.with_user(self.tp).write({'allergy_none_confirmed': True})
        # A script (superuser) is exempt.
        self.env['sports.patient.critical.item'].sudo().create({
            'patient_id': player.id, 'family': 'allergy', 'name': 'Synthetic script nut'})

    # -- AC-4 --------------------------------------------------------------
    def test_pill_and_card_ask_first(self):
        player = self._new_player()
        pills = {p['key']: p for p in player.with_user(self.tp)._sc_medical_pills(tp=True)}
        self.assertEqual(pills['allergy']['level_label'], 'Not provided')
        self.assertTrue(pills['allergy']['epipen_unset'])
        self.assertEqual(pills['allergy']['tone'], pills['medical_alert']['tone'])  # grey (unset)
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=injuries' % player.id)
        sheet = tree.xpath('//dialog[@id="sc_med_player_allergy_%s"]' % player.id)[0]
        card = sheet.xpath('.//section[@data-sc-section="medical.allergy.epipen"]')[0]
        self.assertEqual(card.get('data-sc-edit-open-on-load'), '1')
        self.assertEqual(card.xpath('.//*[@data-sc-med-epipen-state]/@data-sc-med-epipen-state'), ['unset'])
        self.assertEqual(sorted(card.xpath('.//input[@type="radio"][@data-sc-med-set="allergy_epipen_state"]/@value')),
                         ['no', 'yes'])
        # AC-7: one line — the label, then the Oui / Non slider pill, empty.
        ask = card.xpath('.//*[@data-sc-med-epipen-ask]')[0]
        self.assertEqual(ask.get('role'), 'radiogroup')
        label = ask.xpath('./span[contains(@class, "o_sc_med_epipen_ask_label")]')[0]
        self.assertEqual(ask.get('aria-labelledby'), label.get('id'))
        self.assertEqual(label.text_content().strip(), 'EpiPen')
        pill = ask.xpath('./div[contains(@class, "o_sc_toggle_pill")]')[0]
        self.assertEqual([' '.join(o.text_content().split()) for o in pill.xpath('./label')], ['Yes', 'No'])
        self.assertFalse(pill.xpath('.//input[@checked]'))
        self.assertTrue(sheet.xpath('.//*[@data-sc-med-epipen-first]'))
        self.assertFalse(sheet.xpath('.//button[@data-sc-list-add-toggle]'))
        self.assertTrue(sheet.xpath('.//input[@data-sc-med-set="allergy_none_confirmed"][@disabled]'))
        player.sudo().write({'allergy_epipen_state': 'yes'})
        _text, tree = self._get('/my/player?player_id=%s&tab=injuries' % player.id)
        sheet = tree.xpath('//dialog[@id="sc_med_player_allergy_%s"]' % player.id)[0]
        self.assertFalse(sheet.xpath('.//*[@data-sc-med-epipen-first]'))
        self.assertTrue(sheet.xpath('.//button[@data-sc-list-add-toggle]'))
        self.assertIsNone(sheet.xpath('.//section[@data-sc-section="medical.allergy.epipen"]')[0].get(
            'data-sc-edit-open-on-load'))

    # -- AC-5 --------------------------------------------------------------
    def test_todo_to_the_creator(self):
        player = self._new_player(user=self.tp)
        todos = self._todos(player)
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos.user_id, self.tp)
        self.assertEqual(todos.summary, 'Complete the medical file (allergies/EpiPen)')
        # Never twice.
        player.sudo()._sc_raise_epipen_todos()
        self.assertEqual(len(self._todos(player)), 1)
        # Answered: done (an archived / removed activity is no longer open).
        player.with_user(self.tp).write({'allergy_epipen_state': 'no'})
        self.assertFalse(self._todos(player))
        # The superuser (scripts, imports) raises none.
        self.assertFalse(self._todos(self._new_player(first_name='Script')))

    # -- AC-6 --------------------------------------------------------------
    def test_french(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        self.tp.write({'lang': 'fr_CA'})
        player = self._new_player(user=self.tp)
        self.assertEqual(self._todos(player).summary, 'Compléter le dossier médical (allergies/EpiPen)')
        pills = {p['key']: p for p in player.with_user(self.tp).with_context(lang='fr_CA')._sc_medical_pills(tp=True)}
        self.assertEqual(pills['allergy']['level_label'], 'Non renseigné')
        with self.assertRaisesRegex(ValidationError, 'EpiPen'):
            self.env['sports.patient.critical.item'].with_user(self.tp).with_context(lang='fr_CA').create({
                'patient_id': player.id, 'family': 'allergy', 'name': 'Synthetic nut'})


class _Tours1717:

    def test_epipen_first_tour(self):
        player = self._new_player(user=self.tp)
        self.start_tour('/my/player?player_id=%s&team_id=%s&tab=injuries' % (player.id, self.team_a.id),
                        'sc_1717_epipen_first', login='pc.tp@example.com')
        self.assertEqual(player.sudo().allergy_epipen_state, 'no')
        self.assertFalse(self._todos(player))


@tagged('post_install', '-at_install')
class TestEpiPenGatePhone1717(_Tours1717, EpiPen1717Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestEpiPenGateLaptop1717(_Tours1717, EpiPen1717Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
