"""Task 1654 — the life-threatening (critical) items of a player's allergies
and medical alert. Synthetic fixtures only.

Acceptance criteria covered here:

* SUG-1 The rule-based suggester splits the details (commas, semicolons,
  lines, « et » / « and ») and keeps the segments with an urgent cue (EpiPen,
  sévère, anaphyla*…), else the whole text; EpiPen when the segment says so,
  or when the player had EpiPen and there is one item; nothing for no text.
* LVL-1 An item added makes its family « Urgent » (EpiPen follows the
  allergy items); the last one removed -> « Not urgent » when details remain,
  else « None known »; each change posts an internal note and stamps the
  family (« Updated on … by … »).
* LVL-2 « Urgent » can't be chosen without an item (« Add the
  life-threatening item first… »); a creation « Urgent » with details, or
  the legacy edit form (no item editor) with details, gets its items
  suggested; « None known » removes the family's items.
* LVL-3 EpiPen goes with an allergy item only.
* ACL-1 Coaches read the items of their team's players, never write them
  nor the medical fields (also through RPC); therapists write; nobody reads
  another team's items.
* APP-1 POST /my/app/critical/add and /<id>/delete answer like a save of the
  family level (field, value, refresh, also EpiPen); 403 for a coach or a
  player out of reach; 400 for an empty name.
* APP-2 The popup lists the items under the level line (a read fragment),
  with a remove button and an add form for therapists only; the urgent pill
  names its items.
* MIG-1 Migration 19.0.1.107.0: « Urgent » families without items get the
  suggested items and the player is flagged « to validate »; idempotent.
* TOUR-1 (test_critical_items_tours_1654) a therapist adds « Arachides »
  with EpiPen -> urgent and the pill names it; removing it -> « Not urgent ».
"""
import importlib.util
import json
import os

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.models.patient_critical_item import suggest_critical_items
from odoo.addons.bemade_sports_clinic.tests.test_medical_alerts_1630 import MedicalCommon

URGENT_MSG = 'Add the life-threatening item first: « Urgent » needs at least one.'


def _migration():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'migrations', '19.0.1.107.0', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('sc_1654_post_migrate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Critical1654Common(MedicalCommon):

    def setUp(self):
        super().setUp()
        self.player.sudo().write({
            'allergy_level': 'minor', 'allergy_epipen': False, 'allergy_details': 'Synthetic kiwi',
            'medical_alert_level': 'none', 'medical_alert_details': False,
        })
        self.Item = self.env['sports.patient.critical.item']

    def _items(self, family='allergy'):
        return self.Item.sudo().search([('patient_id', '=', self.player.id), ('family', '=', family)])

    def _post(self, url, **data):
        data['csrf_token'] = self._csrf()
        return self.url_open(url, data=data, allow_redirects=False)


@tagged('post_install', '-at_install')
class TestCriticalItems1654(Critical1654Common):

    # -- SUG-1 --------------------------------------------------------------
    def test_suggester(self):
        self.assertEqual(suggest_critical_items('allergy', ''), [])
        self.assertEqual(suggest_critical_items('allergy', 'Synthetic kiwi'),
                         [{'name': 'Synthetic kiwi', 'epipen': False, 'action': False}])
        self.assertEqual(suggest_critical_items('allergy', 'Synthetic kiwi', epipen=True)[0]['epipen'], True)
        got = suggest_critical_items('allergy', 'Pollen, arachides sévère (EpiPen); lactose et noix anaphylaxie')
        self.assertEqual([(i['name'], i['epipen']) for i in got], [('arachides', True), ('noix', False)])
        got = suggest_critical_items('medical_alert', 'Asthme léger\nÉpilepsie grave')
        self.assertEqual([(i['name'], i['epipen']) for i in got], [('Épilepsie', False)])
        # Two items: the player's EpiPen is not guessed onto either.
        got = suggest_critical_items('allergy', 'kiwi severe, noix severe', epipen=True)
        self.assertEqual([i['epipen'] for i in got], [False, False])

    # -- LVL-1 --------------------------------------------------------------
    def test_items_drive_the_level(self):
        player = self.player.with_user(self.tp)
        before = len(self.player.sudo().message_ids)
        item = self.Item.with_user(self.tp).create({
            'patient_id': self.player.id, 'family': 'allergy', 'name': '  Synthetic peanut ', 'epipen': True})
        self.assertEqual(item.name, 'Synthetic peanut')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.allergy_level, self.player.allergy_epipen), ('urgent', True))
        self.assertIn('PC TP', self.player.allergy_updated_info)
        notes = self.player.sudo().message_ids[:len(self.player.sudo().message_ids) - before]
        self.assertTrue(any('Synthetic peanut' in (m.body or '') for m in notes))
        second = self.Item.with_user(self.tp).create({
            'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic bee'})
        item.unlink()
        self.player.invalidate_recordset()
        self.assertEqual((self.player.allergy_level, self.player.allergy_epipen), ('urgent', False))
        second.with_user(self.tp).unlink()
        self.player.invalidate_recordset()
        self.assertEqual(self.player.allergy_level, 'minor', 'details remain')
        # Medical alert: no details -> back to « None known ».
        alert = self.Item.with_user(self.tp).create({
            'patient_id': self.player.id, 'family': 'medical_alert', 'name': 'Synthetic epilepsy'})
        self.assertEqual(player.medical_alert_level, 'urgent')
        alert.with_user(self.tp).unlink()
        self.player.invalidate_recordset()
        self.assertEqual(self.player.medical_alert_level, 'none')
        self.assertTrue(self.player.medical_alert_updated_info)

    # -- LVL-2 --------------------------------------------------------------
    def test_urgent_needs_an_item(self):
        player = self.player.with_user(self.tp)
        with self.assertRaises(ValidationError) as caught:
            player.write({'allergy_level': 'urgent'})
        self.assertEqual(caught.exception.args[0], URGENT_MSG)
        self.Item.with_user(self.tp).create({
            'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic peanut'})
        player.write({'allergy_level': 'minor'})  # the items stay; « Urgent » again is fine
        player.write({'allergy_level': 'urgent'})
        self.assertEqual(len(self._items()), 1)
        # « None known » removes the family's items.
        player.write({'allergy_level': 'none'})
        self.assertFalse(self._items())
        self.assertFalse(player.allergy_details)
        # The legacy edit form (no item editor, sc_critical_suggest): with
        # details, the items are suggested; without, refused.
        legacy = player.with_context(sc_critical_suggest=True)
        with self.assertRaises(ValidationError):
            legacy.write({'allergy_level': 'urgent'})
        legacy.write({'allergy_level': 'urgent', 'allergy_details': 'Synthetic bee severe, synthetic dust'})
        self.assertEqual(self._items().mapped('name'), ['Synthetic bee'])
        self.assertEqual(player.allergy_level, 'urgent')
        # A creation « Urgent » without details is refused, with details it
        # gets its items suggested.
        itp = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Critical Synthetic Admin', 'login': 'critical1654.admin@example.com',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('bemade_sports_clinic.group_sports_clinic_user').id,
                self.env.ref('bemade_sports_clinic.group_sports_clinic_admin').id,
            ])],
        })
        Patient = self.env['sports.patient'].with_user(itp)
        with self.assertRaises(ValidationError):
            Patient.create({'first_name': 'Syn', 'last_name': 'Nodetails', 'medical_alert_level': 'urgent'})
        created = Patient.create({'first_name': 'Syn', 'last_name': 'Details', 'medical_alert_level': 'urgent',
                                  'medical_alert_details': 'Synthetic diabetes'})
        self.assertEqual(created.sudo().critical_item_ids.mapped('name'), ['Synthetic diabetes'])
        self.assertEqual(created.medical_alert_level, 'urgent')

    # -- LVL-3 --------------------------------------------------------------
    def test_epipen_allergy_only(self):
        with self.assertRaises(ValidationError):
            self.Item.with_user(self.tp).create({
                'patient_id': self.player.id, 'family': 'medical_alert', 'name': 'Synthetic', 'epipen': True})

    # -- ACL-1 --------------------------------------------------------------
    def test_coach_reads_never_writes(self):
        item = self.Item.with_user(self.tp).create({
            'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic peanut'})
        other = self.Item.sudo().with_context(sc_critical_quiet=True).create({
            'patient_id': self.player_b.id, 'family': 'allergy', 'name': 'Synthetic other'})
        Coach = self.Item.with_user(self.coach)
        self.assertEqual(Coach.search([]).ids, item.ids, 'own team only')
        self.assertEqual(item.with_user(self.coach).name, 'Synthetic peanut')
        with self.assertRaises(AccessError):
            Coach.create({'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic coach'})
        with self.assertRaises(AccessError):
            item.with_user(self.coach).write({'name': 'Synthetic coach'})
        with self.assertRaises(AccessError):
            item.with_user(self.coach).unlink()
        with self.assertRaises(AccessError):
            self.player.with_user(self.coach).write({'allergy_details': 'Synthetic coach'})
        # The therapist reads no other team's items either.
        self.assertFalse(self.Item.with_user(self.tp).search([('id', '=', other.id)]))

    # -- APP-1 --------------------------------------------------------------
    def test_add_and_delete_routes(self):
        self._login_tp()
        resp = self._post('/my/app/critical/add', patient_id=self.player.id, family='allergy',
                          name='Synthetic peanut', epipen='1', action='Synthetic: inject, call 911')
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        payload = resp.json()
        self.assertEqual((payload['field'], payload['value']), ('allergy_level', 'urgent'))
        self.assertEqual(payload['also']['allergy_epipen']['value'], '1')
        self.assertTrue(any(p.startswith('sports.patient:%s:' % self.player.id) for p in payload['refresh']))
        item = self._items()
        self.assertEqual((item.name, item.epipen, item.action),
                         ('Synthetic peanut', True, 'Synthetic: inject, call 911'))
        with mute_logger('odoo.http'):
            resp = self._post('/my/app/critical/add', patient_id=self.player.id, family='allergy', name='  ')
            self.assertEqual(resp.status_code, 400)
            resp = self._post('/my/app/critical/add', patient_id=self.player_b.id, family='allergy', name='X')
            self.assertEqual(resp.status_code, 403)
        resp = self._post('/my/app/critical/%s/delete' % item.id)
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertEqual(resp.json()['value'], 'minor')
        self.assertFalse(self._items())
        # A coach: 403 on both.
        keep = self.Item.sudo().with_context(sc_critical_quiet=True).create({
            'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic keep'})
        self._login_coach()
        with mute_logger('odoo.http'):
            resp = self._post('/my/app/critical/add', patient_id=self.player.id, family='allergy', name='X')
            self.assertEqual(resp.status_code, 403)
            resp = self._post('/my/app/critical/%s/delete' % keep.id)
            self.assertEqual(resp.status_code, 403)
        self.assertTrue(keep.exists())

    # -- APP-2 --------------------------------------------------------------
    def test_popup_lists_items(self):
        self.Item.with_user(self.tp).create({
            'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic peanut', 'epipen': True,
            'action': 'Synthetic action'})
        self._login_tp()
        tree = self._tree()
        pill = self._pills(tree)['allergy']
        self.assertIn('Synthetic peanut', pill.text_content())
        card = self._sheet(tree, 'allergy').xpath('.//*[@data-sc-edit-card="medical-allergy"]')[0]
        children = card.xpath('./*')
        self.assertIn('o_sc_med_sheet_top', children[0].get('class'))
        crit = card.xpath('./*[contains(@class, "o_sc_critical")]')[0]
        self.assertEqual(crit.get('data-sc-fragment'), 'sports.patient:%s:critical-allergy' % self.player.id)
        self.assertIn('Synthetic peanut', crit.text_content())
        self.assertIn('Synthetic action', crit.text_content())
        self.assertTrue(crit.xpath('.//*[@data-sc-med-epipen]'))
        self.assertEqual(len(crit.xpath('.//button[@data-sc-critical-delete]')), 1)
        form = card.xpath('.//form[@data-sc-critical-add]')
        self.assertEqual(len(form), 1)
        self.assertTrue(form[0].xpath('ancestor::*[@data-sc-edit-view="edit"]'))
        self.assertTrue(form[0].xpath('.//input[@name="epipen"]'))
        self.assertTrue(self._sheet(tree, 'medical_alert').xpath(
            './/form[@data-sc-critical-add]') and not self._sheet(tree, 'medical_alert').xpath(
            './/form[@data-sc-critical-add]//input[@name="epipen"]'), 'no EpiPen on a medical alert')
        # The coach reads the list, without the remove button nor the form.
        self._login_coach()
        sheet = self._sheet(self._tree(), 'allergy')
        self.assertIn('Synthetic peanut', sheet.text_content())
        self.assertFalse(sheet.xpath('.//button[@data-sc-critical-delete] | .//form[@data-sc-critical-add]'))

    # -- MIG-1 --------------------------------------------------------------
    def test_migration_suggests_and_flags(self):
        self.player.sudo().write({'allergy_level': 'urgent', 'allergy_epipen': True,
                                  'allergy_details': 'Synthetic pollen, synthetic peanut severe (EpiPen)',
                                  'medical_alert_review': False})
        self.player_b.sudo().write({'medical_alert_level': 'urgent', 'medical_alert_details': False,
                                    'medical_alert_review': False})
        module = _migration()
        counts = module.convert_urgent_players(self.env)
        self.assertEqual(self._items().mapped('name'), ['synthetic peanut'])
        self.assertTrue(self._items().epipen)
        self.assertGreaterEqual(counts['items'], 1)
        self.assertTrue(self.player.medical_alert_review)
        self.assertTrue(self.player_b.medical_alert_review, 'urgent without text: to validate')
        self.assertEqual(self.player.allergy_details, 'Synthetic pollen, synthetic peanut severe (EpiPen)')
        again = module.convert_urgent_players(self.env)
        self.assertEqual((again['items'], again['players_flagged']), (0, 0))
        self.assertEqual(len(self._items()), 1)
        json.dumps(counts)  # counts only, serialisable for the log
