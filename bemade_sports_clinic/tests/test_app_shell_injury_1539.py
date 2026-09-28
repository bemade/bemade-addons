"""Task 1539 — injuries on the app shell: new injury (device draft +
« Créer »), injury edit (saved on blur, status / visibility instant with
undo). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-I1 (AC1) Switch OFF: /my/patient/injury/new, the « created » landing
  and /my/injury/edit render today's templates; with the switch ON the
  clinic's modal fragments still render today's form bodies (no shell).
* UC-I2 (AC4) New injury: every typed field is a DEVICE draft keyed under
  ``sports.patient.<id>.new_injury.``; opening the page creates nothing; the
  form posts to today's create route; the « created » landing carries the
  draft-clear marker; therapist-only fields are not rendered for a coach.
* UC-I3 (AC3/AC5) Injury edit: server autosave fields; the status and the
  visibility are instant segmented fields for therapists only; a coach sees
  neither the internal notes nor the delete action, and cannot reword a
  verified diagnosis; the delete sheet posts to today's route with CSRF.
* UC-I4 (AC5) A hidden injury never reaches a coach, on either page.
* UC-N1 (AC1) Switch OFF: the notes page and the note history render
  today's templates.
* UC-N2 (AC3/AC4) Notes page in the shell: « Ajouter » is a device draft
  posting to today's route (therapists only); only the notes the viewer
  authored are editable in place (server autosave); the « added » landing
  drops the draft.
* UC-N3 (AC5) Note history as a timeline: a coach gets the external rows
  only (even with ?scope=internal), a therapist all of them + the scope
  filter.
"""
import json
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellInjury1539(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.injury.sudo().write({'internal_notes': 'TP-only synthetic remark',
                                 'external_notes': 'Visible synthetic remark'})
        cls.hidden = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Hidden synthetic injury',
            'hidden_from_coaches': True,
        })
        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'T1539 Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': now, 'date_end': now + timedelta(hours=2),
            'state': 'confirmed', 'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        cls.new_url = '/my/patient/injury/new?patient_id=%s' % cls.player.id
        cls.edit_url = '/my/injury/edit?injury_id=%s' % cls.injury.id

    @staticmethod
    def _owl(tree):
        out = {}
        for node in tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'):
            props = json.loads(node.get('props'))
            out[props.get('field') or props.get('name')] = props
        return out

    # -- UC-I1 -----------------------------------------------------------
    def test_switch_off_legacy(self):
        self._login_tp()
        text, tree = self._get(self.new_url)
        self.assertIn('id="injury_date_na"', text)
        self.assertIsNone(self._shell(tree))
        text, tree = self._get(self.edit_url)
        self.assertIn('id="deleteInjuryModal"', text)
        self.assertIsNone(self._shell(tree))

    def test_clinic_fragments_stay_legacy_with_switch_on(self):
        self._switch(True)
        self._login_tp()
        for url in ('/my/injury/%s/form/fragment?clinic_id=%s' % (self.injury.id, self.clinic.id),
                    '/my/patient/injury/new/fragment?patient_id=%s&clinic_id=%s'
                    % (self.player.id, self.clinic.id)):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertNotIn('data-sc-app-shell', resp.text)
            self.assertNotIn('owl-component', resp.text)
            self.assertIn('name="csrf_token"', resp.text)

    # -- UC-I2 -----------------------------------------------------------
    def test_new_injury_is_a_device_draft(self):
        self._switch(True)
        count = self.env['sports.patient.injury'].search_count([('patient_id', '=', self.player.id)])
        self._login_coach()
        _text, tree = self._get(self.new_url)
        self.assertIsNotNone(self._shell(tree))
        owl = self._owl(tree)
        prefix = 'sports.patient.%s.new_injury.' % self.player.id
        for name in ('diagnosis', 'injury_date', 'external_notes'):
            self.assertEqual(owl[name]['mode'], 'draft', name)
            self.assertEqual(owl[name]['draftKey'], prefix + name)
        self.assertEqual(owl['injury_date']['naName'], 'injury_date_na')
        for name in ('internal_notes', 'parental_consent', 'predicted_resolution_date'):
            self.assertNotIn(name, owl, name)
        form = tree.xpath('//form[@data-sc-form="injury.new"]')[0]
        self.assertEqual(form.get('action'), '/my/patient/injury/create')
        self._login_tp()
        _text, tree = self._get(self.new_url)
        owl = self._owl(tree)
        for name in ('internal_notes', 'parental_consent', 'predicted_resolution_date'):
            self.assertIn(name, owl, name)
        # Opening the page (twice) created nothing.
        self.assertEqual(self.env['sports.patient.injury'].search_count(
            [('patient_id', '=', self.player.id)]), count)

    def test_create_lands_on_draft_clear(self):
        self._switch(True)
        self._login_coach()
        count = self.env['sports.patient.injury'].search_count([('patient_id', '=', self.player.id)])
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'diagnosis': 'Synthetic report', 'injury_date': '2026-03-03',
            'external_notes': 'Synthetic external',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.env['sports.patient.injury'].search_count(
            [('patient_id', '=', self.player.id)]), count + 1)
        self.assertIn('data-sc-draft-clear="sports.patient.%s.new_injury."' % self.player.id,
                      resp.text)

    # -- UC-I3 -----------------------------------------------------------
    def test_edit_therapist(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get(self.edit_url)
        owl = self._owl(tree)
        self.assertEqual(owl['stage']['inputType'], 'segmented')
        self.assertTrue(owl['stage']['instant'])
        self.assertEqual(owl['hidden_from_coaches']['value'], '0')
        self.assertEqual(owl['sc_injury_date']['inputType'], 'date_na')
        for name in ('diagnosis', 'external_notes', 'internal_notes', 'predicted_resolution_date',
                     'resolution_date', 'parental_consent'):
            self.assertEqual(owl[name]['mode'], 'server', name)
        self.assertIn('TP-only synthetic remark', text)
        form = tree.xpath('//dialog[@id="sc_delete_injury_sheet"]//form')[0]
        self.assertEqual(form.get('action'), '/my/injury/delete')
        self.assertEqual(form.xpath('.//input[@name="injury_id"]/@value'), [str(self.injury.id)])
        self.assertTrue(form.xpath('.//input[@name="csrf_token"]/@value')[0])

    def test_edit_coach(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get(self.edit_url)
        owl = self._owl(tree)
        self.assertEqual(set(owl), {'sc_injury_date', 'external_notes'})
        self.assertIn('Visible synthetic remark', text)
        self.assertNotIn('TP-only synthetic remark', text)
        self.assertFalse(tree.xpath('//*[@data-sc-action="injury.delete"]'))
        self.assertTrue(tree.xpath('//*[@data-sc-section="injury.stage.readonly"]'))

    # -- UC-I4 -----------------------------------------------------------
    def test_hidden_injury_never_reaches_a_coach(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/player?player_id=%s&tab=injuries' % self.player.id)
        self.assertNotIn(str(self.hidden.id), tree.xpath('//*[@data-sc-injury-id]/@data-sc-injury-id'))
        resp = self.url_open('/my/injury/edit?injury_id=%s' % self.hidden.id)
        self.assertNotEqual(resp.status_code, 200)
        self.assertNotIn('Hidden synthetic injury', resp.text)


@tagged('post_install', '-at_install')
class TestAppShellNotes1539(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'T1539 Notes TP2', 'login': 't1539.notes.tp2@example.com',
            'group_ids': [Command.set([portal, tp_g])],
        })
        Note = env['sports.treatment.note']
        cls.mine = Note.create({'patient_id': cls.player.id, 'note': 'My synthetic note',
                                'user_id': cls.tp.id, 'date': '2026-01-05'})
        cls.theirs = Note.create({'patient_id': cls.player.id, 'note': 'Their synthetic note',
                                  'user_id': cls.tp2.id, 'date': '2026-01-04'})
        # One internal + one external history row, written as the therapist.
        cls.injury.with_user(cls.tp).write({'internal_notes': 'Internal synthetic history'})
        cls.injury.with_user(cls.tp).write({'external_notes': 'External synthetic history'})
        cls.notes_url = '/my/patient/notes?patient_id=%s' % cls.player.id
        cls.history_url = '/my/injury/%s/notes/history' % cls.injury.id

    # -- UC-N1 -----------------------------------------------------------
    def test_switch_off_legacy(self):
        self._login_tp()
        for url in (self.notes_url, self.history_url):
            text, tree = self._get(url)
            self.assertIn('<table', text, url)
            self.assertIsNone(self._shell(tree), url)

    # -- UC-N2 -----------------------------------------------------------
    def test_notes_page_editable_by_author_only(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.notes_url)
        self.assertIsNotNone(self._shell(tree))
        mine = tree.xpath('//*[@data-sc-note-id="%s"]//owl-component' % self.mine.id)
        self.assertEqual(json.loads(mine[0].get('props'))['field'], 'note')
        self.assertFalse(tree.xpath('//*[@data-sc-note-id="%s"]//owl-component' % self.theirs.id))
        form = tree.xpath('//form[@data-sc-form="notes.add"]')[0]
        self.assertEqual(form.get('action'), '/my/injury/note/add')
        self.assertEqual(form.xpath('.//input[@name="return_url"]/@value'), [self.notes_url])
        text, tree = self._get(self.notes_url + '&success=note_added')
        self.assertEqual(tree.xpath('//*[@data-sc-draft-clear]/@data-sc-draft-clear'),
                         ['sports.patient.%s.new_note.' % self.player.id])
        # A coach reads the notes (as today) but adds / edits none.
        self._login_coach()
        _text, tree = self._get(self.notes_url)
        self.assertFalse(tree.xpath('//form[@data-sc-form="notes.add"]'))
        self.assertFalse(tree.xpath('//owl-component'))

    # -- UC-N3 -----------------------------------------------------------
    def test_history_scopes(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get(self.history_url)
        scopes = tree.xpath('//*[@data-sc-section="history.list"]/li/@data-sc-scope')
        self.assertIn('internal', scopes)
        self.assertIn('external', scopes)
        self.assertTrue(tree.xpath('//*[@data-sc-section="history.scope"]'))
        self._login_coach()
        for url in (self.history_url, self.history_url + '?scope=internal'):
            text, tree = self._get(url)
            scopes = tree.xpath('//*[@data-sc-section="history.list"]/li/@data-sc-scope')
            self.assertEqual(set(scopes), {'external'}, url)
            self.assertNotIn('Internal synthetic history', text)
            self.assertFalse(tree.xpath('//*[@data-sc-section="history.scope"]'))
