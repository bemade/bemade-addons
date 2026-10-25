"""Task 1630 — allergies + medical-alert pills (owner + MC 2026-10-21).
Synthetic fixtures only (invented texts).

Acceptance criteria:

* HDR-1 Player header: two pills, « Allergies » and « Medical alert », left
  of the pencil (in the header's top row, after the name), each coloured by
  its level (« None » grey, « Not urgent » yellow, « Urgent » red, « Not
  specified » outline); the Allergies pill carries the EpiPen icon only when
  ticked. The pills are a read fragment (no island) refreshed by a save.
* HDR-2 Popup: each pill opens its sheet with the level, EpiPen and the
  details; a therapist gets a pencil there opening the edit view (level
  select with « Not specified », details, EpiPen for the allergies). The
  header's own edit view no longer edits the allergies.
* COACH-1 Coach: read-only — only the yellow / red pills, with their popup
  (details) and no pencil, no island; nothing for « None » / « Not
  specified »; never « Other medical history ».
* DOS-1 Clinic dossier: the same pills (+ popups) replace the allergies
  banner.
* INFO-1 Infos tab: an « Other medical history » card for therapists (read
  view + pencil + autosave textarea); a coach does not get it.
* SAVE-1 Save registry: a therapist saves every new field (level « » =
  Not specified, EpiPen 1/0, details); a coach gets 403 on each; the legacy
  ``allergies`` is no longer savable.
* FLD-1 Field access: a portal coach reads the level / details / EpiPen,
  never « Other medical history »; the legacy ``allergies`` is system-only.
* CRE-1 Create forms: the app's new-player form (therapists) posts the
  levels / details / EpiPen (levels optional); the legacy edit form posts
  them too.
* LEG-1 Legacy portal pages read the compact « Allergies (urgent –
  life-threatening, EpiPen): … » lines (a coach: yellow / red only).

Task 1677: the levels are computed from structured lists (fixtures through
``set_medical``); the popup's editor (HDR-2's level select, details, EpiPen
segmented control) and the level / details / EpiPen saves (SAVE-1) are
replaced by the lists — see test_medical_lists_1677. The create forms no
longer take levels or details (CRE-1).
"""
import json

from odoo import Command
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin
from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

HERO = '//*[@data-sc-section="player.hero"]'


class MedicalCommon(FragmentsMixin, PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_medical(cls.player, allergies=[('Synthetic kiwi', True)], epipen=True, none_condition=True)
        cls.player.sudo().write({'medical_history_other': 'Synthetic fracture 2020'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _tree(self, tab='injuries'):
        _text, tree = self._get(self._url(tab=tab))
        return tree

    @staticmethod
    def _pills(tree, section='player.medical'):
        return {node.get('data-sc-med-pill'): node for node in tree.xpath(
            '//*[@data-sc-section="%s"]//button[@data-sc-med-pill]' % section)}

    def _sheet(self, tree, key, scope='player'):
        nodes = tree.xpath('//dialog[@id="sc_med_%s_%s_%s"]' % (scope, key, self.player.id))
        return nodes[0] if nodes else None


@tagged('post_install', '-at_install')
class TestMedicalHeader1630(MedicalCommon):

    # -- HDR-1 -------------------------------------------------------------
    def test_two_pills_with_tones_and_epipen(self):
        self._login_tp()
        tree = self._tree()
        hero = tree.xpath(HERO)[0]
        top = hero.xpath('./*[contains(@class, "o_sc_hero_top")]')[0]
        self.assertTrue(top.xpath('./*[contains(@class, "o_sc_hero_head")]'))
        holder = top.xpath('./*[@data-sc-section="player.medical"]')[0]
        self.assertEqual(holder.get('data-sc-fragment'), 'sports.patient:%s:medical-pills' % self.player.id)
        self.assertFalse(holder.xpath('.//owl-component'))
        pills = self._pills(tree)
        self.assertEqual(list(pills), ['allergy', 'medical_alert'])
        self.assertIn('o_sc_med_urgent', pills['allergy'].get('class'))
        self.assertIn('o_sc_med_none', pills['medical_alert'].get('class'))
        self.assertTrue(pills['allergy'].xpath('.//*[@data-sc-med-epipen]'))
        self.assertFalse(pills['medical_alert'].xpath('.//*[@data-sc-med-epipen]'))
        self.assertEqual(pills['allergy'].get('data-sc-sheet-open'), 'sc_med_player_allergy_%s' % self.player.id)
        # Tones of the other levels; EpiPen gone when unticked. Task 1677:
        # « Not specified » is grey too.
        for items, tone in (([('Synthetic kiwi', False)], 'o_sc_med_minor'), ([], 'o_sc_med_none')):
            set_medical(self.player, allergies=items, epipen=False)
            pill = self._pills(self._tree())['allergy']
            self.assertIn(tone, pill.get('class'), items)
            self.assertFalse(pill.xpath('.//*[@data-sc-med-epipen]'), items)
        # No allergies banner any more.
        self.assertFalse(tree.xpath('//*[@data-sc-section="player.allergies"]'))

    def test_pills_fragment_refreshes_after_save(self):
        self._login_tp()
        url = self._url(tab='injuries')
        key = 'sports.patient:%s:medical-pills' % self.player.id
        self.assertFragmentMatchesPage(url, key)
        resp = self.url_open('/my/app/medical/item/add', data={
            'patient_id': self.player.id, 'family': 'medical_alert', 'name': 'Synthetic asthma',
            'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertRefreshes(payload, key)
        self.assertRefreshes(payload, 'sports.patient:%s:medical-medical_alert-head' % self.player.id)
        node = self._fragment(url, key)
        pill = node.xpath('.//button[@data-sc-med-pill="medical_alert"]')[0]
        self.assertIn('o_sc_med_minor', pill.get('class'))

    # -- HDR-2 -------------------------------------------------------------
    def test_popups_outside_fragments(self):
        """Task 1677: the popup's content is test_medical_lists_1677 (UI-1);
        here: the sheets stay outside every read fragment and the header's
        own edit view does not edit the allergies."""
        self._login_tp()
        tree = self._tree()
        sheet = self._sheet(tree, 'allergy')
        self.assertIsNotNone(sheet)
        self.assertIn('Synthetic kiwi', sheet.text_content())
        for node in tree.xpath('//*[@data-sc-fragment]'):
            self.assertFalse(node.xpath('.//dialog[starts-with(@id, "sc_med_")]'), node.get('data-sc-fragment'))
        hero = tree.xpath(HERO)[0]
        self.assertFalse(hero.xpath('.//*[@data-sc-edit-view="edit"]//owl-component[contains(@props, \'"allergies"\')]'))
        self.assertFalse(hero.xpath('.//*[@data-sc-section="player.allergies.edit"]'))

    # -- COACH-1 ------------------------------------------------------------
    def test_coach_sees_yellow_red_only_read_only(self):
        self._login_coach()
        tree = self._tree()
        pills = self._pills(tree)
        self.assertEqual(list(pills), ['allergy'], 'no pill for « None »')
        sheet = self._sheet(tree, 'allergy')
        self.assertIn('Synthetic kiwi', sheet.text_content())
        self.assertFalse(sheet.xpath('.//*[@data-sc-edit-toggle] | .//owl-component | .//*[@data-sc-edit-view="edit"]'))
        self.assertIsNone(self._sheet(tree, 'medical_alert'))
        set_medical(self.player, allergies=[], conditions=[('Synthetic asthma', False)])
        tree = self._tree()
        self.assertEqual(list(self._pills(tree)), ['medical_alert'])
        self.assertIn('o_sc_med_minor', self._pills(tree)['medical_alert'].get('class'))
        self.assertIn('Synthetic asthma', self._sheet(tree, 'medical_alert').text_content())
        set_medical(self.player, allergies=[], conditions=[], none_allergy=True, none_condition=False)
        tree = self._tree()
        self.assertEqual(self._pills(tree), {})
        holder = tree.xpath('//*[@data-sc-section="player.medical"]')
        self.assertEqual(len(holder), 1, 'the holder stays (a fragment)')
        # Never « Other medical history ».
        page = self._get(self._url(tab='info'))[0]
        self.assertNotIn('Synthetic fracture 2020', page)
        self.assertFalse(self._tree('info').xpath('//*[@data-sc-edit-card="medical-history"]'))

    # -- INFO-1 -------------------------------------------------------------
    def test_infos_card_other_medical_history(self):
        self._login_tp()
        tree = self._tree('info')
        card = tree.xpath('//*[@data-sc-edit-card="medical-history"]')[0]
        read = card.xpath('.//*[@data-sc-edit-view="read"]')[0]
        self.assertIn('Synthetic fracture 2020', read.text_content())
        self.assertTrue(card.xpath('.//button[@data-sc-edit-toggle]'))
        props = [json.loads(p) for p in card.xpath('.//owl-component/@props')]
        self.assertEqual([(p['field'], p['inputType']) for p in props], [('medical_history_other', 'textarea')])
        payload = self._saved(self.player, 'medical_history_other', 'Synthetic surgery 2021')
        self.assertRefreshes(payload, 'sports.patient:%s:medical-history' % self.player.id)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.medical_history_other, 'Synthetic surgery 2021')

    # -- SAVE-1 -------------------------------------------------------------
    def test_therapist_saves_other_history_only(self):
        """Task 1677: « Other medical history » is the one generic save left
        (the lists have their own routes; the levels are computed)."""
        self._login_tp()
        self._saved(self.player, 'medical_history_other', '')
        self.player.invalidate_recordset()
        self.assertFalse(self.player.medical_history_other)
        with mute_logger('odoo.http', 'odoo.addons.bemade_sports_clinic.controllers.app_shell'):
            for field in ('allergy_level', 'allergy_details', 'allergy_epipen',
                          'medical_alert_level', 'medical_alert_details', 'allergies'):
                self.assertEqual(self._save(self.player, field, 'x').status_code, 403, field)

    def test_coach_gets_403_on_every_field(self):
        self._login_coach()
        with mute_logger('odoo.http', 'odoo.addons.bemade_sports_clinic.controllers.app_shell'):
            for field, value in (('allergy_level', 'minor'), ('allergy_details', 'x'),
                                 ('allergy_epipen', '0'), ('medical_alert_level', 'minor'),
                                 ('medical_alert_details', 'x'), ('medical_history_other', 'x'),
                                 ('allergies', 'x')):
                resp = self._save(self.player, field, value)
                self.assertEqual(resp.status_code, 403, field)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.sudo().allergy_level, 'urgent')

    # -- FLD-1 --------------------------------------------------------------
    def test_field_access(self):
        Patient = self.env['sports.patient']
        for name in ('allergy_level', 'allergy_details', 'allergy_epipen',
                     'medical_alert_level', 'medical_alert_details',
                     # Task 1677
                     'allergy_epipen_note', 'allergy_none_confirmed', 'medical_none_confirmed'):
            field = Patient._fields[name]
            self.assertTrue(Patient.with_user(self.coach)._has_field_access(field, 'read'), name)
            self.assertTrue(Patient.with_user(self.tp)._has_field_access(field, 'read'), name)
            self.assertFalse(Patient.with_user(self.plain)._has_field_access(field, 'read'), name)
        other = Patient._fields['medical_history_other']
        self.assertFalse(Patient.with_user(self.coach)._has_field_access(other, 'read'))
        self.assertTrue(Patient.with_user(self.tp)._has_field_access(other, 'read'))
        legacy = Patient._fields['allergies']
        for user in (self.coach, self.tp):
            self.assertFalse(Patient.with_user(user)._has_field_access(legacy, 'read'))
        review = Patient._fields['medical_alert_review']
        self.assertFalse(Patient.with_user(self.tp)._has_field_access(review, 'read'), 'back-end only')

    # -- CRE-1 --------------------------------------------------------------
    def test_app_create_form_fields(self):
        # Task 1655: a therapist creates players inline (key information
        # only — the medical fields are set on the player page afterwards).
        self._login_tp()
        resp = self.url_open('/my/player/create?first_name=Nobody&last_name=Synthetic', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        _text, tree = self._get('/my/players?add=1')
        form = tree.xpath('//form[@data-sc-player-add]')[0]
        for name in ('allergy_level', 'allergy_details', 'allergy_epipen', 'allergies'):
            self.assertFalse(form.xpath('.//*[@name="%s"]' % name), name)
        # Task 1677: the legacy POST (/my/player/create/save) takes « Other
        # medical history » only — the lists are filled on the player page.
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'Syn', 'last_name': 'Created',
            'date_of_birth': '2010-01-01', 'team_ids': str(self.team_a.id),
            'allergy_level': 'urgent', 'allergy_details': 'Synthetic bee', 'allergy_epipen': '1',
            'allergy_epipen_present': '1', 'medical_history_other': 'Synthetic surgery',
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303), resp.text[:300])
        created = self.env['sports.patient'].search([('last_name', '=', 'Created')])
        self.assertEqual(len(created), 1)
        self.assertEqual((created.allergy_level, created.allergy_epipen, created.allergy_details),
                         (False, False, False))
        self.assertEqual(created.medical_history_other, 'Synthetic surgery')
        self.assertFalse(created.sudo().critical_item_ids)

    def test_coach_create_ignores_medical_fields(self):
        self._login_coach()
        _text, tree = self._get('/my/player/create?first_name=Nobody&last_name=Synthetic')
        self.assertFalse(tree.xpath('//form[@data-sc-form="player.create"]//*[@name="allergy_level"]'))

    def test_vals_from_post(self):
        Patient = self.env['sports.patient']
        self.assertEqual(Patient._sc_medical_vals_from_post({}), {})
        vals = Patient._sc_medical_vals_from_post({
            'allergy_level': 'bogus', 'medical_alert_level': 'minor', 'allergy_details': '  x ',
            'medical_history_other': ' y ', 'allergy_epipen_present': '1'})
        self.assertEqual(vals, {'medical_history_other': 'y'})

    # -- LEG-1 --------------------------------------------------------------
    def test_summary_lines(self):
        player = self.player.with_user(self.tp)
        lines = [line['text'] for line in player._sc_medical_summary_lines(tp=True)]
        self.assertEqual(lines, ['Allergies (urgent – life-threatening, EpiPen): '
                                 'Synthetic kiwi (life-threatening)'])
        coach_lines = [line['text'] for line in self.player.with_user(self.coach)._sc_medical_summary_lines()]
        self.assertEqual(coach_lines, lines)
        self.assertEqual(self.player.with_user(self.plain).sudo(False)._sc_medical_pills(tp=True), [])

    def test_legacy_player_page(self):
        self._switch(False)
        self._login_coach()
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Synthetic kiwi', resp.text)
        # Task 1677: an item without « Risque vital » is yellow — a coach
        # reads it; « None known » shows nothing to a coach.
        set_medical(self.player, allergies=[('Synthetic kiwi', False)])
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertIn('Synthetic kiwi', resp.text)
        set_medical(self.player, allergies=[], none_allergy=True)
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertNotIn('Allergies (none known)', resp.text, 'a coach never sees « None »')
        self._login_tp()
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertEqual(resp.status_code, 200)
        set_medical(self.player, allergies=[('Synthetic kiwi', True)], none_allergy=False)
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertIn('Synthetic kiwi', resp.text)

    def test_legacy_edit_form_saves(self):
        self._switch(False)
        self._login_tp()
        resp = self.url_open('/my/player/edit?patient_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('name="allergy_level"', resp.text)
        self.assertIn('name="medical_history_other"', resp.text)
        self.assertNotIn('name="allergies"', resp.text)


@tagged('post_install', '-at_install')
class TestMedicalDossier1630(Clinic1540Common):

    def test_dossier_pills(self):
        set_medical(self.player, allergies=[('Synthetic pollen', False)], conditions=[],
                    none_allergy=False, none_condition=False)
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player.id))
        hero = tree.xpath('//*[@data-sc-section="clinic.dossier.hero"]')[0]
        pills = hero.xpath('.//*[@data-sc-section="clinic.dossier.medical"]//button[@data-sc-med-pill]')
        self.assertEqual([p.get('data-sc-med-pill') for p in pills], ['allergy', 'medical_alert'])
        self.assertIn('o_sc_med_minor', pills[0].get('class'))
        self.assertIn('o_sc_med_none', pills[1].get('class'))
        self.assertEqual(pills[1].get('data-sc-med-level'), 'unset')
        sheet = tree.xpath('//dialog[@id="sc_med_clinic_allergy_%s"]' % self.player.id)[0]
        self.assertIn('Synthetic pollen', sheet.text_content())
        self.assertTrue(sheet.xpath('.//button[@data-sc-edit-toggle]'))
        self.assertFalse(hero.xpath('.//*[contains(@class, "o_sc_banner")]'), 'no allergies banner')


@tagged('post_install', '-at_install')
class TestMedicalRolesRegistry1630(MedicalCommon):

    def test_registry_keys(self):
        from odoo.addons.bemade_sports_clinic.models import sc_app_roles as registry
        coach, tp = self.coach._sc_app_roles(), self.tp._sc_app_roles()
        self.assertTrue(registry.can('patient.medical_alerts', coach))
        self.assertTrue(registry.can('patient.medical_alerts', tp))
        self.assertFalse(registry.can('patient.medical_history', coach))
        self.assertTrue(registry.can('patient.medical_history', tp))
        with self.assertRaises(KeyError):
            registry.can('patient.allergies', tp)

    def test_backend_review_list(self):
        action = self.env.ref('bemade_sports_clinic.action_patient_medical_review')
        self.assertEqual(action.res_model, 'sports.patient')
        self.assertIn('search_default_medical_alert_review', action.context)
        menu = self.env.ref('bemade_sports_clinic.sports_clinic_medical_review_menu')
        self.assertEqual(menu.parent_id, self.env.ref('bemade_sports_clinic.sports_clinic_staff_menu'))
        arch = self.env.ref('bemade_sports_clinic.sports_patient_view_list_medical_review').arch_db
        for name in ('team_ids', 'allergy_level', 'allergy_epipen', 'allergy_details',
                     'medical_alert_level', 'medical_alert_details', 'medical_alert_review',
                     'allergy_critical_ids', 'medical_alert_critical_ids'):
            self.assertIn('name="%s"' % name, arch, name)
        search = self.env.ref('bemade_sports_clinic.sports_patient_view_search').arch_db
        self.assertIn('name="medical_alert_review"', search)
        flagged = self.env['sports.patient'].create({
            'first_name': 'Syn', 'last_name': 'Flagged', 'medical_alert_review': True,
            'team_ids': [Command.set(self.team_a.ids)]})
        found = self.env['sports.patient'].search([('medical_alert_review', '=', True)])
        self.assertIn(flagged, found)
        self.assertNotIn(self.player, found)
        form = self.env.ref('bemade_sports_clinic.sports_patient_view_form').arch_db
        self.assertNotIn('name="allergies"', form)
        self.assertIn('name="allergy_level"', form)
