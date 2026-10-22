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
"""
import json

from odoo import Command
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

HERO = '//*[@data-sc-section="player.hero"]'


class MedicalCommon(FragmentsMixin, PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.sudo().write({
            'allergy_level': 'urgent', 'allergy_epipen': True,
            'allergy_details': 'Synthetic kiwi', 'medical_alert_level': 'none',
            'medical_alert_details': False, 'medical_history_other': 'Synthetic fracture 2020',
        })

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
        # Tones of the other levels; EpiPen gone when unticked.
        for level, tone in (('minor', 'o_sc_med_minor'), (False, 'o_sc_med_unset')):
            self.player.sudo().write({'allergy_level': level, 'allergy_epipen': False})
            pill = self._pills(self._tree())['allergy']
            self.assertIn(tone, pill.get('class'), level)
            self.assertFalse(pill.xpath('.//*[@data-sc-med-epipen]'), level)
        # No allergies banner any more.
        self.assertFalse(tree.xpath('//*[@data-sc-section="player.allergies"]'))

    def test_pills_fragment_refreshes_after_save(self):
        self._login_tp()
        url = self._url(tab='injuries')
        key = 'sports.patient:%s:medical-pills' % self.player.id
        self.assertFragmentMatchesPage(url, key)
        payload = self._saved(self.player, 'medical_alert_level', 'minor')
        self.assertRefreshes(payload, key)
        self.assertRefreshes(payload, 'sports.patient:%s:medical-medical_alert' % self.player.id)
        node = self._fragment(url, key)
        pill = node.xpath('.//button[@data-sc-med-pill="medical_alert"]')[0]
        self.assertIn('o_sc_med_minor', pill.get('class'))

    # -- HDR-2 -------------------------------------------------------------
    def test_popup_and_therapist_pencil(self):
        self._login_tp()
        tree = self._tree()
        sheet = self._sheet(tree, 'allergy')
        self.assertIsNotNone(sheet)
        read = sheet.xpath('.//*[@data-sc-edit-view="read"]')[0]
        self.assertEqual(read.get('data-sc-fragment'), 'sports.patient:%s:medical-allergy' % self.player.id)
        self.assertIn('Synthetic kiwi', read.text_content())
        self.assertIn('Urgent', read.text_content())
        self.assertTrue(read.xpath('.//*[@data-sc-med-epipen]'))
        self.assertFalse(read.xpath('.//owl-component'))
        card = sheet.xpath('.//*[@data-sc-edit-card="medical-allergy"]')[0]
        # Review round 1 (owner 2026-10-22): the app's standard edit pencil —
        # icon only, top-right of the popup content (the level line's row,
        # not the dialog head with its close ✕), visible while editing.
        toggles = card.xpath('.//button[@data-sc-edit-toggle]')
        self.assertEqual(len(toggles), 1)
        toggle = toggles[0]
        self.assertIn('o_sc_icon_btn', toggle.get('class'))
        self.assertEqual(toggle.get('data-sc-action'), 'medical.edit')
        self.assertEqual((toggle.get('aria-label'), toggle.get('title')), ('Edit', 'Edit'))
        self.assertEqual(toggle.text_content().strip(), '', 'icon only')
        self.assertTrue(toggle.xpath('.//*[local-name()="svg"]'))
        self.assertFalse(toggle.xpath('ancestor::*[@data-sc-edit-view]'), 'hidden while editing')
        self.assertFalse(toggle.xpath('ancestor::*[contains(@class, "o_sc_sheet_head")]'))
        top = card.xpath('./*[contains(@class, "o_sc_med_sheet_top")]')
        self.assertEqual(len(top), 1)
        self.assertIs(card.xpath('./*')[0], top[0], 'the first line of the popup')
        self.assertIs(toggle.getparent(), top[0])
        self.assertIs(top[0].xpath('./*')[-1], toggle, 'right of the level line')
        self.assertTrue(top[0].xpath('./*[@data-sc-edit-view="read"]//*[contains(@class, "o_sc_med_level_line")]'))
        # No « Edit » text button any more.
        self.assertFalse(sheet.xpath('.//*[contains(@class, "o_sc_med_edit_row")]'))
        self.assertFalse([b for b in sheet.xpath('.//button') if b.text_content().strip() == 'Edit'])
        edit = card.xpath('.//*[@data-sc-edit-view="edit"]')[0]
        self.assertEqual(edit.get('hidden'), 'hidden')
        props = [json.loads(p) for p in edit.xpath('.//owl-component/@props')]
        self.assertEqual([p['field'] for p in props], ['allergy_level', 'allergy_epipen', 'allergy_details'])
        self.assertEqual(props[0]['inputType'], 'select')
        # Task 1653: a set level offers the three levels only.
        self.assertEqual(props[0]['options'][0], ['none', 'None known'])
        self.assertEqual([o[0] for o in props[0]['options']], ['none', 'minor', 'urgent'])
        self.assertEqual(props[0]['value'], 'urgent')
        self.assertEqual(props[1]['value'], '1')
        alert = self._sheet(tree, 'medical_alert')
        alert_props = [json.loads(p)['field'] for p in alert.xpath('.//owl-component/@props')]
        self.assertEqual(alert_props, ['medical_alert_level', 'medical_alert_details'])
        self.assertIn('No details.', alert.xpath('.//*[@data-sc-edit-view="read"]')[0].text_content())
        # The sheets are outside every read fragment.
        for node in tree.xpath('//*[@data-sc-fragment]'):
            self.assertFalse(node.xpath('.//dialog[starts-with(@id, "sc_med_")]'), node.get('data-sc-fragment'))
        # The header pencil no longer edits the allergies.
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
        self.player.sudo().write({'allergy_level': False, 'medical_alert_level': 'minor',
                                  'medical_alert_details': 'Synthetic asthma'})
        tree = self._tree()
        self.assertEqual(list(self._pills(tree)), ['medical_alert'])
        self.assertIn('o_sc_med_minor', self._pills(tree)['medical_alert'].get('class'))
        self.assertIn('Synthetic asthma', self._sheet(tree, 'medical_alert').text_content())
        self.player.sudo().write({'allergy_level': 'none', 'medical_alert_level': False})
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
    def test_therapist_saves_every_field(self):
        self._login_tp()
        cases = (
            ('allergy_level', 'minor', 'minor', 'Not urgent'),
            ('allergy_epipen', '0', False, 'No'),
            ('allergy_epipen', '1', True, 'Yes'),
            ('allergy_details', '  Synthetic latex  ', 'Synthetic latex', None),
            ('medical_alert_level', 'urgent', 'urgent', 'Urgent – life-threatening'),
            ('medical_alert_details', 'Synthetic epilepsy', 'Synthetic epilepsy', None),
            ('medical_history_other', '', False, None),
        )
        for field, value, expected, display in cases:
            payload = self._saved(self.player, field, value)
            self.player.invalidate_recordset()
            self.assertEqual(self.player[field], expected, field)
            if display is not None:
                self.assertEqual(payload.get('display'), display, field)
        with mute_logger('odoo.http', 'odoo.addons.bemade_sports_clinic.controllers.app_shell'):
            resp = self._save(self.player, 'allergy_level', 'bogus')
            self.assertNotEqual(resp.status_code, 200)
            # Task 1653: a set level can't go back to « Not specified ».
            resp = self._save(self.player, 'allergy_level', '')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['message'], 'Please choose a level.')

    def test_coach_gets_403_on_every_field(self):
        self._login_coach()
        with mute_logger('odoo.http', 'odoo.addons.bemade_sports_clinic.controllers.app_shell'):
            for field, value in (('allergy_level', 'minor'), ('allergy_details', 'x'),
                                 ('allergy_epipen', '0'), ('medical_alert_level', 'minor'),
                                 ('medical_alert_details', 'x'), ('medical_history_other', 'x'),
                                 ('allergies', 'x')):
                resp = self._save(self.player, field, value)
                self.assertEqual(resp.status_code, 403, field)
        self._login_tp()
        with mute_logger('odoo.http', 'odoo.addons.bemade_sports_clinic.controllers.app_shell'):
            resp = self._save(self.player, 'allergies', 'x')
        self.assertEqual(resp.status_code, 403, 'the legacy field is not savable')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.sudo().allergy_level, 'urgent')

    # -- FLD-1 --------------------------------------------------------------
    def test_field_access(self):
        Patient = self.env['sports.patient']
        for name in ('allergy_level', 'allergy_details', 'allergy_epipen',
                     'medical_alert_level', 'medical_alert_details'):
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
        self._login_tp()
        _text, tree = self._get('/my/player/create?first_name=Nobody&last_name=Synthetic')
        form = tree.xpath('//form[@data-sc-form="player.create"]')[0]
        for name in ('allergy_level', 'allergy_details', 'allergy_epipen',
                     'medical_alert_level', 'medical_alert_details'):
            self.assertTrue(form.xpath('.//*[@name="%s"]' % name), name)
        self.assertFalse(form.xpath('.//*[@name="allergies"]'))
        self.assertFalse(form.xpath('.//select[@name="allergy_level"][@required]'), 'optional')
        options = form.xpath('.//select[@name="allergy_level"]/option/@value')
        self.assertEqual(options, ['', 'none', 'minor', 'urgent'])
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'Syn', 'last_name': 'Created',
            'date_of_birth': '2010-01-01', 'team_ids': str(self.team_a.id),
            'allergy_level': 'urgent', 'allergy_details': 'Synthetic bee', 'allergy_epipen': '1',
            'allergy_epipen_present': '1', 'medical_alert_level': '', 'medical_alert_details': '',
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303), resp.text[:300])
        created = self.env['sports.patient'].search([('last_name', '=', 'Created')])
        self.assertEqual(len(created), 1)
        self.assertEqual((created.allergy_level, created.allergy_epipen, created.allergy_details),
                         ('urgent', True, 'Synthetic bee'))
        self.assertFalse(created.medical_alert_level)

    def test_coach_create_ignores_medical_fields(self):
        self._login_coach()
        _text, tree = self._get('/my/player/create?first_name=Nobody&last_name=Synthetic')
        self.assertFalse(tree.xpath('//form[@data-sc-form="player.create"]//*[@name="allergy_level"]'))

    def test_vals_from_post(self):
        Patient = self.env['sports.patient']
        self.assertEqual(Patient._sc_medical_vals_from_post({}), {})
        vals = Patient._sc_medical_vals_from_post({
            'allergy_level': 'bogus', 'medical_alert_level': 'minor', 'allergy_details': '  x ',
            'medical_history_other': '', 'allergy_epipen_present': '1'})
        self.assertEqual(vals, {'allergy_level': False, 'medical_alert_level': 'minor',
                                'allergy_details': 'x', 'medical_history_other': False,
                                'allergy_epipen': False})

    # -- LEG-1 --------------------------------------------------------------
    def test_summary_lines(self):
        player = self.player.with_user(self.tp)
        lines = [line['text'] for line in player._sc_medical_summary_lines(tp=True)]
        self.assertEqual(lines, ['Allergies (urgent – life-threatening, EpiPen): Synthetic kiwi',
                                 'Medical alert (none known)'])
        coach_lines = [line['text'] for line in self.player.with_user(self.coach)._sc_medical_summary_lines()]
        self.assertEqual(coach_lines, ['Allergies (urgent – life-threatening, EpiPen): Synthetic kiwi'])
        self.assertEqual(self.player.with_user(self.plain).sudo(False)._sc_medical_pills(tp=True), [])

    def test_legacy_player_page(self):
        self._switch(False)
        self._login_coach()
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Synthetic kiwi', resp.text)
        self.player.sudo().write({'allergy_level': 'none'})
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertNotIn('Synthetic kiwi', resp.text, 'a coach never sees « None »')
        self._login_tp()
        resp = self.url_open('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Synthetic kiwi', resp.text)

    def test_legacy_edit_form_saves(self):
        self._switch(False)
        self._login_tp()
        resp = self.url_open('/my/player/edit?patient_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('name="allergy_level"', resp.text)
        self.assertIn('name="medical_history_other"', resp.text)
        self.assertNotIn('name="allergies"', resp.text)


@tagged('post_install', '-at_install')
class TestMedicalDossier1630(Clinic1540Common):

    def test_dossier_pills(self):
        self.player.sudo().write({'allergy_level': 'minor', 'allergy_details': 'Synthetic pollen',
                                  'medical_alert_level': False})
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player.id))
        hero = tree.xpath('//*[@data-sc-section="clinic.dossier.hero"]')[0]
        pills = hero.xpath('.//*[@data-sc-section="clinic.dossier.medical"]//button[@data-sc-med-pill]')
        self.assertEqual([p.get('data-sc-med-pill') for p in pills], ['allergy', 'medical_alert'])
        self.assertIn('o_sc_med_minor', pills[0].get('class'))
        self.assertIn('o_sc_med_unset', pills[1].get('class'))
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
                     'medical_alert_level', 'medical_alert_details', 'medical_alert_review'):
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
