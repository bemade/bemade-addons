"""Task 1677 — allergies and medical alerts as structured card lists (owner
2026-10-24). Synthetic fixtures only (this repository is public).

Use case: a therapist opens a player's « Allergies » pill and keeps a short
list — one card per allergy (name + « Risque vital ») and an EpiPen card
(ticked + where it is). The « Medical alert » pill is the same list for the
conditions, each with its first-aid instructions. The pills turn red / yellow
/ grey by themselves; a coach reads it all, never changes it.

Acceptance criteria:

* PILL-1 Levels are computed from the lists, per family: a life-threatening
  item -> « Urgent » (red); items, none life-threatening -> « Not urgent »
  (yellow); an empty list with « none known » ticked -> « None known »
  (grey); an empty list not confirmed -> « Not specified » (grey too, but
  still asked by the #1628 To-Do). A write of a level is ignored.
* CRUD-1 A therapist adds, edits and deletes items through the popup routes
  (``/my/app/medical/item/add`` / ``<id>/save`` / ``<id>/delete``) and the
  ORM; each answer carries the family's level and tone and refreshes the
  player's fragments; each change stamps the family and posts an internal
  note; an empty name is refused (400).
* CRUD-2 A coach reads the items (ORM) but can't create / write / delete
  them nor the player's medical fields (AccessError); every popup route
  answers 403 to a coach and for a player out of the therapist's teams.
* IMM-1 An item's player and family can't be changed by a non-superuser
  (AccessError); the superuser (merges) can.
* EPI-1 The EpiPen card: ticked -> the note shows (read view) and is
  editable (edit view); unticking clears the note; the note field of the
  edit view is hidden while unticked.
* NONE-1 « No known allergy / condition »: a checkbox only while the list
  is empty (therapist); refused with items; adding an item unticks it.
* OLD-1 « Old text (to validate) »: the former details (else the legacy
  allergies text), read-only, only while the player is flagged « to
  validate ».
* UI-1 The popup: the family title + its pill (a read fragment), the EpiPen
  card (allergies only), the list header « + Ajouter » with its add panel,
  one card per item (pencil -> edit view with the fields and the trash can),
  no OWL island; a coach gets the same content without any control.
* TODO-1 #1628: a family is complete once its list has an item or « none
  known » is ticked.
* CARD-1 Card pills (#1652): red only, naming the life-threatening items
  (allergies and conditions), the EpiPen icon on the allergy one.
* MIG-1 Migration 19.0.1.117.0: #1654 items are kept; former details and the
  legacy text are split into items (life-threatening on an urgent cue, none
  for a « Not urgent » family; EpiPen OR'ed); « aucune » variants and
  « None known » levels tick « none known »; converted players are flagged
  « to validate »; the levels are recomputed; idempotent.
* TOUR-1 (test_medical_lists_tours_1677) phone + laptop.
"""
import importlib.util
import json
import os

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.models.medical_alerts import suggest_medical_items
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin
from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

QUIET_LOGS = ('odoo.http', 'odoo.addons.bemade_sports_clinic.controllers.app_shell',
              'odoo.addons.bemade_sports_clinic.controllers.app_critical_items')


def _migration():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'migrations', '19.0.1.117.0', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('sc_1677_post_migrate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MedicalLists1677Common(FragmentsMixin, PlayerInlineCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)
        set_medical(self.player, allergies=[('Synthetic kiwi', False)], conditions=[],
                    epipen=False, none_allergy=False, none_condition=False)
        self.player.sudo().write({'medical_alert_review': False, 'allergy_details': False,
                                  'medical_alert_details': False})
        self.Item = self.env['sports.patient.critical.item']

    def _items(self, family='allergy'):
        return self.Item.sudo().search([('patient_id', '=', self.player.id), ('family', '=', family)])

    def _post(self, url, **data):
        data['csrf_token'] = self._csrf()
        return self.url_open(url, data=data, allow_redirects=False)

    def _tree(self, tab='injuries'):
        _text, tree = self._get(self._url(tab=tab))
        return tree

    def _sheet(self, tree, key, scope='player'):
        nodes = tree.xpath('//dialog[@id="sc_med_%s_%s_%s"]' % (scope, key, self.player.id))
        return nodes[0] if nodes else None

    def _levels(self):
        self.player.invalidate_recordset()
        player = self.player.sudo()
        return player.allergy_level, player.medical_alert_level


@tagged('post_install', '-at_install')
class TestMedicalLists1677(MedicalLists1677Common):

    # -- PILL-1 -------------------------------------------------------------
    def test_levels_follow_the_lists(self):
        player = self.player
        set_medical(player, allergies=[('Synthetic kiwi', False), ('Synthetic pollen', False)],
                    conditions=[('Synthetic asthma', True, 'Synthetic inhaler')])
        self.assertEqual(self._levels(), ('minor', 'urgent'))
        set_medical(player, allergies=[('Synthetic peanut', True)], conditions=[])
        self.assertEqual(self._levels(), ('urgent', False))
        set_medical(player, allergies=[], conditions=[], none_allergy=True, none_condition=False)
        self.assertEqual(self._levels(), ('none', False))
        # Ticking « Risque vital » on an item turns the family red.
        set_medical(player, allergies=[('Synthetic kiwi', False)], none_allergy=False)
        item = self._items()
        self.assertEqual(self._levels()[0], 'minor')
        item.sudo().write({'life_threatening': True})
        self.assertEqual(self._levels()[0], 'urgent')
        item.sudo().unlink()
        self.assertEqual(self._levels()[0], False)
        # A level is never written (an old client, a script).
        player.sudo().write({'allergy_level': 'urgent', 'medical_alert_level': 'none'})
        self.assertEqual(self._levels(), (False, False))

    def test_pill_tones(self):
        self._login_tp()
        cases = (
            (dict(allergies=[('Synthetic peanut', True)]), 'urgent', 'urgent'),
            (dict(allergies=[('Synthetic kiwi', False)]), 'minor', 'minor'),
            (dict(allergies=[], none_allergy=True), 'none', 'none'),
            (dict(allergies=[], none_allergy=False), 'none', 'unset'),
        )
        for state, tone, level in cases:
            set_medical(self.player, **state)
            tree = self._tree()
            pill = tree.xpath('//*[@data-sc-section="player.medical"]//button[@data-sc-med-pill="allergy"]')[0]
            self.assertIn('o_sc_med_%s' % tone, pill.get('class'), state)
            self.assertEqual(pill.get('data-sc-med-level'), level, state)
            head = self._sheet(tree, 'allergy').xpath('.//*[@data-sc-med-head]')[0]
            self.assertIn('o_sc_med_%s' % tone, head.get('class'), state)
        # The red pill names its life-threatening items only.
        set_medical(self.player, allergies=[('Synthetic peanut', True), ('Synthetic kiwi', False)])
        pill = self._tree().xpath('//button[@data-sc-med-pill="allergy"]')[0]
        self.assertEqual(' '.join(pill.text_content().split()), 'Synthetic peanut')

    # -- CRUD-1 -------------------------------------------------------------
    def test_therapist_add_edit_delete_routes(self):
        self._login_tp()
        resp = self._post('/my/app/medical/item/add', patient_id=self.player.id, family='medical_alert',
                          name='  Synthetic epilepsy ', life_threatening='1', first_aid_note=' Synthetic recovery position ')
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertEqual((payload['family'], payload['level'], payload['tone']), ('medical_alert', 'urgent', 'urgent'))
        self.assertRefreshes(payload, 'sports.patient:%s:medical-pills' % self.player.id)
        self.assertRefreshes(payload, 'sports.patient:%s:medical-medical_alert-items' % self.player.id)
        item = self._items('medical_alert')
        self.assertEqual((item.name, item.life_threatening, item.first_aid_note),
                         ('Synthetic epilepsy', True, 'Synthetic recovery position'))
        self.assertEqual(payload['item_id'], item.id)
        self.player.invalidate_recordset()
        self.assertIn('PC TP', self.player.sudo().medical_alert_updated_info)
        notes = self.player.sudo().message_ids.filtered(lambda m: 'Synthetic epilepsy' in (m.body or ''))
        self.assertTrue(notes)
        self.assertTrue(all(m.subtype_id == self.env.ref('mail.mt_note') for m in notes))
        # Edit: the posted keys only.
        resp = self._post('/my/app/medical/item/%s/save' % item.id, life_threatening='0')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual((resp.json()['level'], resp.json()['tone']), ('minor', 'minor'))
        item.invalidate_recordset()
        self.assertEqual((item.name, item.life_threatening), ('Synthetic epilepsy', False))
        resp = self._post('/my/app/medical/item/%s/save' % item.id, name='Synthetic seizures',
                          first_aid_note='')
        self.assertEqual(resp.status_code, 200, resp.text)
        item.invalidate_recordset()
        self.assertEqual((item.name, item.first_aid_note), ('Synthetic seizures', False))
        with mute_logger(*QUIET_LOGS):
            resp = self._post('/my/app/medical/item/%s/save' % item.id, name='  ')
            self.assertEqual(resp.status_code, 400)
            resp = self._post('/my/app/medical/item/add', patient_id=self.player.id, family='allergy', name='')
            self.assertEqual(resp.status_code, 400)
            resp = self._post('/my/app/medical/item/add', patient_id=self.player.id, family='bogus', name='x')
            self.assertEqual(resp.status_code, 400)
        # Delete.
        resp = self._post('/my/app/medical/item/%s/delete' % item.id)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['level'], 'unset')
        self.assertFalse(item.exists())
        # The allergies' first-aid field is not taken (conditions only).
        resp = self._post('/my/app/medical/item/add', patient_id=self.player.id, family='allergy',
                          name='Synthetic bee', first_aid_note='x')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertFalse(self._items().filtered(lambda i: i.name == 'Synthetic bee').first_aid_note)

    def test_therapist_orm(self):
        Item = self.Item.with_user(self.tp)
        item = Item.create({'patient_id': self.player.id, 'family': 'allergy', 'name': 'Synthetic latex',
                            'life_threatening': True})
        self.assertEqual(self._levels()[0], 'urgent')
        item.write({'name': 'Synthetic latex gloves'})
        item.unlink()
        self.assertEqual(self._levels()[0], 'minor')
        with self.assertRaises(ValidationError):
            Item.create({'patient_id': self.player.id, 'family': 'allergy', 'name': '   '})

    # -- CRUD-2 -------------------------------------------------------------
    def test_coach_reads_never_writes(self):
        item = self._items()
        Item = self.Item.with_user(self.coach)
        self.assertEqual(Item.search([('patient_id', '=', self.player.id)]), item)
        with self.assertRaises(AccessError):
            Item.create({'patient_id': self.player.id, 'family': 'allergy', 'name': 'x'})
        with self.assertRaises(AccessError):
            item.with_user(self.coach).write({'life_threatening': True})
        with self.assertRaises(AccessError):
            item.with_user(self.coach).unlink()
        for vals in ({'allergy_epipen': True}, {'allergy_epipen_note': 'x'},
                     {'allergy_none_confirmed': True}, {'medical_none_confirmed': True},
                     {'critical_item_ids': [Command.create({'family': 'allergy', 'name': 'x'})]}):
            with self.assertRaises(AccessError, msg=vals):
                self.player.with_user(self.coach).write(vals)
        # Nobody reads another team's items.
        other = set_medical(self.player_b, allergies=[('Synthetic sesame', True)])
        self.assertFalse(self.Item.with_user(self.tp).search([('patient_id', '=', other.id)]))
        self.assertFalse(self.Item.with_user(self.coach).search([('patient_id', '=', other.id)]))

    def test_coach_routes_refused(self):
        item = self._items()
        self._login_coach()
        with mute_logger(*QUIET_LOGS):
            for url, data in (
                    ('/my/app/medical/item/add', {'patient_id': self.player.id, 'family': 'allergy', 'name': 'x'}),
                    ('/my/app/medical/item/%s/save' % item.id, {'name': 'x'}),
                    ('/my/app/medical/item/%s/delete' % item.id, {}),
                    ('/my/app/medical/%s/set' % self.player.id, {'field': 'allergy_epipen', 'value': '1'})):
                self.assertEqual(self._post(url, **data).status_code, 403, url)
        self.assertTrue(item.exists())
        # A therapist, for a player out of their teams; an unknown field.
        other = set_medical(self.player_b, allergies=[('Synthetic sesame', True)])
        other_item = self.Item.sudo().search([('patient_id', '=', other.id)])
        self._login_tp()
        with mute_logger(*QUIET_LOGS):
            for url, data in (
                    ('/my/app/medical/item/add', {'patient_id': other.id, 'family': 'allergy', 'name': 'x'}),
                    ('/my/app/medical/item/%s/save' % other_item.id, {'name': 'x'}),
                    ('/my/app/medical/item/%s/delete' % other_item.id, {}),
                    ('/my/app/medical/%s/set' % other.id, {'field': 'allergy_epipen', 'value': '1'}),
                    ('/my/app/medical/%s/set' % self.player.id, {'field': 'allergy_details', 'value': 'x'}),
                    ('/my/app/medical/%s/set' % self.player.id, {'field': 'allergy_level', 'value': 'urgent'})):
                self.assertEqual(self._post(url, **data).status_code, 403, url)
        self.assertTrue(other_item.exists())
        # The levels / details / EpiPen are no longer generic saves.
        with mute_logger(*QUIET_LOGS):
            for field in ('allergy_level', 'allergy_details', 'allergy_epipen', 'medical_alert_level'):
                self.assertEqual(self._save(self.player, field, 'x').status_code, 403, field)

    # -- IMM-1 --------------------------------------------------------------
    def test_item_player_and_family_immutable(self):
        mine = self._items().with_user(self.tp)
        self.env['sports.team.staff'].create({
            'team_id': self.team_b.id, 'partner_id': self.tp.partner_id.id, 'role': 'therapist'})
        for vals in ({'patient_id': self.player_b.id}, {'family': 'medical_alert'}):
            with self.assertRaises(AccessError, msg=vals):
                mine.write(vals)
        mine.sudo().write({'patient_id': self.player_b.id})  # the superuser (merges)
        self.assertEqual(mine.sudo().patient_id, self.player_b)

    # -- EPI-1 --------------------------------------------------------------
    def test_epipen_card(self):
        self._login_tp()
        set_url = '/my/app/medical/%s/set' % self.player.id
        tree = self._tree()
        card = self._sheet(tree, 'allergy').xpath('.//*[@data-sc-section="medical.allergy.epipen"]')[0]
        self.assertFalse(card.xpath('.//*[@data-sc-med-epipen-note]'))
        self.assertEqual(card.xpath('.//*[@data-sc-med-epipen-note-field]')[0].get('hidden'), 'hidden')
        resp = self._post(set_url, field='allergy_epipen', value='1')
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self._post(set_url, field='allergy_epipen_note', value='  Synthetic front pocket ')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertRefreshes(resp.json(), 'sports.patient:%s:medical-epipen' % self.player.id)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.sudo().allergy_epipen, self.player.sudo().allergy_epipen_note),
                         (True, 'Synthetic front pocket'))
        card = self._sheet(self._tree(), 'allergy').xpath('.//*[@data-sc-section="medical.allergy.epipen"]')[0]
        read = card.xpath('.//*[@data-sc-edit-view="read"]')[0]
        self.assertEqual(read.get('data-sc-fragment'), 'sports.patient:%s:medical-epipen' % self.player.id)
        self.assertIn('Synthetic front pocket', read.text_content())
        self.assertIsNone(card.xpath('.//*[@data-sc-med-epipen-note-field]')[0].get('hidden'))
        self.assertTrue(card.xpath('.//input[@data-sc-med-set="allergy_epipen"][@checked]'))
        # The header pill carries the EpiPen icon.
        pill = self._tree().xpath('//button[@data-sc-med-pill="allergy"]')[0]
        self.assertTrue(pill.xpath('.//*[@data-sc-med-epipen]'))
        # Unticking clears the note.
        self._post(set_url, field='allergy_epipen', value='')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.sudo().allergy_epipen, self.player.sudo().allergy_epipen_note), (False, False))
        self.assertIn('PC TP', self.player.sudo().allergy_updated_info)
        # Medical alerts: no EpiPen card.
        self.assertFalse(self._sheet(self._tree(), 'medical_alert').xpath('.//*[@data-sc-section="medical.allergy.epipen"]'))

    # -- NONE-1 -------------------------------------------------------------
    def test_none_known(self):
        self._login_tp()
        tree = self._tree()
        self.assertFalse(self._sheet(tree, 'allergy').xpath('.//input[@data-sc-med-set="allergy_none_confirmed"]'),
                         'not with items')
        self.assertTrue(self._sheet(tree, 'medical_alert').xpath('.//input[@data-sc-med-set="medical_none_confirmed"]'))
        set_url = '/my/app/medical/%s/set' % self.player.id
        with mute_logger(*QUIET_LOGS):
            resp = self._post(set_url, field='allergy_none_confirmed', value='1')
        self.assertEqual(resp.status_code, 400)
        resp = self._post(set_url, field='medical_none_confirmed', value='1')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual((resp.json()['level'], resp.json()['tone']), ('none', 'none'))
        self.assertEqual(self._levels()[1], 'none')
        # Adding an item unticks it.
        self._post('/my/app/medical/item/add', patient_id=self.player.id, family='medical_alert',
                   name='Synthetic asthma')
        self.player.invalidate_recordset()
        self.assertFalse(self.player.sudo().medical_none_confirmed)
        self.assertEqual(self._levels()[1], 'minor')

    # -- OLD-1 --------------------------------------------------------------
    def test_old_text_only_while_flagged(self):
        self.player.sudo().write({'allergy_details': 'Synthetic old allergy text',
                                  'allergies': 'Synthetic legacy text'})
        self._login_tp()
        legacy = '//dialog[@id="sc_med_player_%s_%s"]//*[@data-sc-med-legacy]'
        self.assertFalse(self._tree().xpath(legacy % ('allergy', self.player.id)))
        self.player.sudo().write({'medical_alert_review': True})
        tree = self._tree()
        self.assertEqual(tree.xpath(legacy % ('allergy', self.player.id))[0].text_content(),
                         'Synthetic old allergy text')
        # No details for the medical alert: the legacy text.
        self.assertEqual(tree.xpath(legacy % ('medical_alert', self.player.id))[0].text_content(),
                         'Synthetic legacy text')
        self.assertFalse(tree.xpath('//dialog//textarea[@name="allergy_details"]'), 'read-only')
        self.player.sudo().write({'medical_alert_review': False})
        self.assertFalse(self._tree().xpath(legacy % ('allergy', self.player.id)))

    # -- UI-1 ---------------------------------------------------------------
    def test_popup_structure_therapist(self):
        set_medical(self.player, allergies=[('Synthetic peanut', True), ('Synthetic kiwi', False)],
                    conditions=[('Synthetic asthma', False, 'Synthetic inhaler')])
        self._login_tp()
        tree = self._tree()
        pid = self.player.id
        for key in ('allergy', 'medical_alert'):
            sheet = self._sheet(tree, key)
            self.assertIsNotNone(sheet, key)
            self.assertFalse(sheet.xpath('.//owl-component'), key)
            self.assertEqual(sheet.xpath('.//*[@data-sc-med-head]/..')[0].get('data-sc-fragment'),
                             'sports.patient:%s:medical-%s-head' % (pid, key))
            header = sheet.xpath('.//*[contains(@class, "o_sc_list_header")]//button[@data-sc-list-add-toggle]')[0]
            panel = sheet.xpath('.//details[@id="%s"]' % header.get('aria-controls'))[0]
            self.assertIn('o_sc_list_add_panel', panel.get('class'))
            form = panel.xpath('.//form[@data-sc-med-add]')[0]
            self.assertEqual(form.get('data-sc-family'), key)
            self.assertTrue(form.xpath('.//input[@name="life_threatening"]'))
            self.assertEqual(bool(form.xpath('.//textarea[@name="first_aid_note"]')), key == 'medical_alert')
            items = sheet.xpath('.//ul[@data-sc-fragment="sports.patient:%s:medical-%s-items"]' % (pid, key))[0]
            self.assertEqual(items.get('data-sc-fragment-mode'), 'list')
            cards = items.xpath('./li[@data-sc-med-item]')
            self.assertEqual(len(cards), 2 if key == 'allergy' else 1)
            for card in cards:
                self.assertTrue(card.get('data-sc-fragment-item'))
                self.assertTrue(card.xpath('.//button[@data-sc-edit-toggle]'))
                edit = card.xpath('.//*[@data-sc-edit-view="edit"]')[0]
                self.assertEqual(edit.get('hidden'), 'hidden')
                self.assertTrue(edit.xpath('.//input[@data-sc-med-item-field="name"]'))
                self.assertTrue(edit.xpath('.//input[@data-sc-med-item-field="life_threatening"]'))
                self.assertEqual(bool(edit.xpath('.//textarea[@data-sc-med-item-field="first_aid_note"]')),
                                 key == 'medical_alert')
                self.assertTrue(edit.xpath('.//button[@data-sc-med-item-delete]'))
                read = card.xpath('.//*[@data-sc-edit-view="read"]')[0]
                self.assertEqual(read.get('data-sc-fragment'),
                                 'sports.patient:%s:medical-item-%s' % (pid, card.get('data-sc-med-item')))
        allergy = self._sheet(tree, 'allergy')
        vital = allergy.xpath('.//li[@data-sc-med-vital="1"]')
        self.assertEqual(len(vital), 1)
        self.assertTrue(vital[0].xpath('.//*[@data-sc-med-vital-chip]'))
        self.assertIn('Synthetic inhaler', self._sheet(tree, 'medical_alert').xpath(
            './/*[@data-sc-med-first-aid]')[0].text_content())
        # The fragments render as on the page.
        for key in ('medical-allergy-items', 'medical-allergy-head', 'medical-epipen'):
            self.assertFragmentMatchesPage(self._url(tab='injuries'), 'sports.patient:%s:%s' % (pid, key))
        # The former level selectors / details / #1654 editor are gone.
        self.assertFalse(tree.xpath('//dialog[starts-with(@id, "sc_med_")]//*[@data-sc-critical-add]'
                                    ' | //dialog[starts-with(@id, "sc_med_")]//select'))

    def test_popup_coach_read_only(self):
        set_medical(self.player, allergies=[('Synthetic peanut', True)],
                    conditions=[('Synthetic asthma', False, 'Synthetic inhaler')],
                    epipen=True, epipen_note='Synthetic bag')
        self._login_coach()
        tree = self._tree()
        for key in ('allergy', 'medical_alert'):
            sheet = self._sheet(tree, key)
            self.assertFalse(sheet.xpath(
                './/button[@data-sc-edit-toggle] | .//input | .//textarea | .//form | .//details'
                ' | .//*[@data-sc-edit-view="edit"] | .//*[@data-sc-list-add-toggle]'), key)
        self.assertIn('Synthetic bag', self._sheet(tree, 'allergy').text_content())
        self.assertIn('Synthetic inhaler', self._sheet(tree, 'medical_alert').text_content())
        # Grey families: no pill for a coach.
        set_medical(self.player, allergies=[], conditions=[], none_allergy=True)
        tree = self._tree()
        self.assertFalse(tree.xpath('//button[@data-sc-med-pill]'))

    # -- TODO-1 -------------------------------------------------------------
    def test_incomplete_file(self):
        player = self.player.sudo()
        set_medical(player, allergies=[], conditions=[], none_allergy=False, none_condition=False)
        missing = player._sc_incomplete_items()
        self.assertIn('allergy_level', missing)
        self.assertIn('medical_alert_level', missing)
        set_medical(player, allergies=[('Synthetic kiwi', False)], conditions=[], none_condition=True)
        missing = player._sc_incomplete_items()
        self.assertNotIn('allergy_level', missing)
        self.assertNotIn('medical_alert_level', missing)

    # -- CARD-1 -------------------------------------------------------------
    def test_card_pills(self):
        set_medical(self.player, allergies=[('Synthetic peanut', True), ('Synthetic kiwi', False)],
                    conditions=[('Synthetic asthma', False)], epipen=True)
        pills = self.player.with_user(self.coach)._sc_card_medical_pills()[self.player.id]
        self.assertEqual([(p['key'], p['label'], p['epipen']) for p in pills],
                         [('allergy', 'Synthetic peanut', True)])
        self.assertNotIn('Synthetic kiwi', pills[0]['title'])
        set_medical(self.player, allergies=[('Synthetic kiwi', False)],
                    conditions=[('Synthetic epilepsy', True), ('Synthetic diabetes', True), ('Synthetic asthma', True)])
        pills = self.player.with_user(self.tp)._sc_card_medical_pills()[self.player.id]
        self.assertEqual([(p['key'], p['label'], p['epipen']) for p in pills],
                         [('medical_alert', 'Synthetic epilepsy · Synthetic diabetes +1', False)])
        set_medical(self.player, allergies=[('Synthetic kiwi', False)], conditions=[])
        self.assertEqual(self.player.with_user(self.tp)._sc_card_medical_pills(), {})

    def test_summary_lines(self):
        set_medical(self.player, allergies=[('Synthetic peanut', True), ('Synthetic kiwi', False)],
                    conditions=[], epipen=True, none_condition=True)
        lines = [line['text'] for line in self.player.with_user(self.tp)._sc_medical_summary_lines(tp=True)]
        self.assertEqual(lines, ['Allergies (urgent – life-threatening, EpiPen): '
                                 'Synthetic peanut (life-threatening), Synthetic kiwi'])


@tagged('post_install', '-at_install')
class TestMedicalSuggester1677(MedicalLists1677Common):

    def test_suggester(self):
        self.assertEqual(suggest_medical_items('')['kind'], 'empty')
        self.assertEqual(suggest_medical_items('Aucune allergie connue')['kind'], 'none')
        result = suggest_medical_items('Synthetic peanut (EpiPen), synthetic pollen; asthme')
        self.assertEqual(result['kind'], 'items')
        self.assertTrue(result['epipen'])
        self.assertEqual(result['allergy'], [{'name': 'Synthetic peanut', 'life_threatening': True},
                                             {'name': 'Synthetic pollen', 'life_threatening': False}])
        self.assertEqual(result['medical_alert'], [{'name': 'Asthme', 'life_threatening': False}])
        result = suggest_medical_items('Allergie aux noix sévère et pénicilline')
        self.assertEqual([(i['name'], i['life_threatening']) for i in result['allergy']],
                         [('Noix', True), ('Pénicilline', False)])
        result = suggest_medical_items("pas d'EpiPen, kiwi")
        self.assertFalse(result['epipen'])
        self.assertEqual(result['allergy'], [{'name': 'Kiwi', 'life_threatening': False}])
        # One allergy and EpiPen: that one is life-threatening.
        result = suggest_medical_items('Fruits de mer - EpiPen')
        self.assertEqual(result['allergy'], [{'name': 'Fruits de mer', 'life_threatening': True}])


@tagged('post_install', '-at_install')
class TestMedicalMigration1677(MedicalLists1677Common):

    def _make(self, last, **vals):
        player = self.env['sports.patient'].create(dict({'first_name': 'Syn', 'last_name': last}, **vals))
        return player

    def _old_levels(self, player, allergy=None, medical=None):
        """The stored levels the previous version left (no compute)."""
        self.env.flush_all()
        self.env.cr.execute("UPDATE sports_patient SET allergy_level = %s, medical_alert_level = %s WHERE id = %s",
                            (allergy, medical, player.id))
        player.invalidate_recordset()

    def test_convert_both_paths_and_idempotent(self):
        module = _migration()
        # Staging-like: a #1654 item (now life-threatening) + its details.
        staged = self._make('Staged', allergy_details='Synthetic peanut severe, synthetic kiwi')
        self.Item.sudo().with_context(sc_critical_quiet=True).create({
            'patient_id': staged.id, 'family': 'allergy', 'name': 'Synthetic peanut', 'life_threatening': True})
        self._old_levels(staged, 'urgent', 'none')
        # Staging-like: a « Not urgent » family with details, cue words ignored.
        minor = self._make('Minor', medical_alert_details='Synthetic asthma severe; synthetic migraine')
        self._old_levels(minor, None, 'minor')
        # Prod-like: the legacy text only.
        legacy = self._make('Legacy', allergies='Synthetic shrimp (EpiPen), synthetic pollen; asthme')
        nothing = self._make('Nothing', allergies='Aucune')
        empty = self._make('Empty')
        counts = module.convert(self.env)
        self.assertGreaterEqual(counts['allergy_kept_items'], 1)
        staged.invalidate_recordset()
        self.assertEqual([(i.name, i.life_threatening) for i in staged.critical_item_ids], [('Synthetic peanut', True)])
        self.assertEqual((staged.allergy_level, staged.medical_alert_level), ('urgent', 'none'))
        self.assertTrue(staged.medical_none_confirmed)
        self.assertEqual([(i.family, i.name, i.life_threatening) for i in minor.critical_item_ids],
                         [('medical_alert', 'Synthetic asthma', False), ('medical_alert', 'Synthetic migraine', False)])
        self.assertEqual(minor.medical_alert_level, 'minor')
        self.assertTrue(minor.medical_alert_review)
        self.assertEqual(sorted((i.family, i.name, i.life_threatening) for i in legacy.critical_item_ids),
                         [('allergy', 'Synthetic pollen', False), ('allergy', 'Synthetic shrimp', True),
                          ('medical_alert', 'Asthme', False)])
        self.assertTrue(legacy.allergy_epipen)
        self.assertTrue(legacy.medical_alert_review)
        self.assertEqual((legacy.allergy_level, legacy.medical_alert_level), ('urgent', 'minor'))
        self.assertTrue(nothing.allergy_none_confirmed and nothing.medical_none_confirmed)
        self.assertEqual((nothing.allergy_level, nothing.medical_alert_level), ('none', 'none'))
        self.assertFalse(nothing.medical_alert_review)
        self.assertFalse(empty.critical_item_ids)
        self.assertEqual((empty.allergy_level, empty.medical_alert_level), (False, False))
        self.assertGreaterEqual(counts['scanned'], 5)
        # Idempotent: nothing more on a second run.
        before = self.Item.sudo().search_count([])
        again = module.convert(self.env)
        self.assertEqual(self.Item.sudo().search_count([]), before)
        self.assertEqual(again['allergy_items'] + again['medical_alert_items'], 0)
        self.assertEqual(again['newly_flagged'], 0)
