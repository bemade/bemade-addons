"""Owner review 2026-10-25 (#1675) — in the app, coaches READ the injury's
external note but no longer write it (therapists only). Synthetic fixtures
only.

Acceptance criteria:

* AC-1 ``/my/app/save`` of ``external_notes`` by a coach answers 403 and
  leaves the note (and its history) as it was; a therapist's save still
  answers 200 and writes it.
* AC-2 The coach's open injury card shows the external note and its stamp
  in the read view, with NO pencil and NO editor on it; the therapist's card
  keeps both.
* AC-3 The coach's reports in the app carry no external note: the full-page
  « Report Injury » form (``/my/patient/injury/new``) has no external-note
  field (a therapist's « Add Injury » keeps it), and the create route
  ignores an ``external_notes`` a coach posts — the inline « Report
  Injury » card and the full page alike. The diagnosis is still reported.
* AC-4 The legacy injury save (``/my/injury/save``, full and partial) is not
  an app path for a coach: with the app on, a coach's posted external note
  is ignored there too.
* AC-5 (owner 2026-10-25, supersedes « legacy unchanged ») Legacy portal
  pages (switch off): a coach no longer saves the external note there
  either. The report form has no external-note card for a coach and the
  edit form shows it read-only; a coach's posted external note is dropped
  (create, full save, partial save) with a warning flash — never a 500 —
  and the note is unchanged.
* AC-6 The model refuses ``external_notes`` from a coach (a share user
  without the portal therapist group): ``write`` and ``create`` raise
  AccessError, whatever the path (RPC included). A therapist and the
  superuser (imports, merges, crons) still write it.
"""
import json

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

EXT = 'Synthetic ext 1675 review'


@tagged('post_install', '-at_install')
class TestCoachExternalNoteReadOnly1675(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury.sudo().with_context(mail_notrack=True).write({'external_notes': EXT})

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- helpers ---------------------------------------------------------
    def _save(self, field, value):
        self.injury.invalidate_recordset()
        return self.url_open('/my/app/save/%s/%s' % (self.injury._name, self.injury.id), data={
            'field': field, 'value': value,
            'write_date': fields.Datetime.to_string(self.injury.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)

    def _history_count(self):
        return self.env['sports.injury.note.history'].search_count(
            [('injury_id', '=', self.injury.id), ('scope', '=', 'external')])

    def _external_card(self):
        _text, tree = self._get('/my/player?player_id=%s&tab=injuries&injury=%s'
                                % (self.player.id, self.injury.id))
        cards = tree.xpath('//details[@id="injury-%s"]//*[@data-sc-edit-card="injury-notes-external"]'
                           % self.injury.id)
        self.assertEqual(len(cards), 1)
        return cards[0]

    @staticmethod
    def _fields(node):
        return [(lambda d: d.get('field') or d.get('name'))(json.loads(p)) for p in node.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')]

    def _create(self, **data):
        self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id, **data})
        return self.env['sports.patient.injury'].sudo().search(
            [('patient_id', '=', self.player.id), ('diagnosis', '=', data['diagnosis'])])

    # -- AC-1 ------------------------------------------------------------
    def test_coach_save_refused(self):
        self._login_coach()
        before = self._history_count()
        resp = self._save('external_notes', 'Coach rewrite (synthetic)')
        self.assertEqual(resp.status_code, 403, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, EXT)
        self.assertEqual(self._history_count(), before)

    def test_therapist_still_saves(self):
        self._login_tp()
        resp = self._save('external_notes', 'Therapist update (synthetic)')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'Therapist update (synthetic)')

    # -- AC-2 ------------------------------------------------------------
    def test_coach_card_reads_without_pencil(self):
        self._login_coach()
        card = self._external_card()
        self.assertFalse(card.xpath('.//button[@data-sc-edit-toggle]'))
        self.assertFalse(card.xpath('.//*[@data-sc-edit-view="edit"]'))
        self.assertEqual(self._fields(card), [])
        read = card.xpath('./*[@data-sc-edit-view="read"]')[0]
        self.assertIn(EXT, read.text_content())
        self.assertTrue(read.xpath('.//*[@data-sc-note-stamp="external"]'))

    def test_therapist_card_keeps_pencil(self):
        self._login_tp()
        card = self._external_card()
        self.assertEqual(len(card.xpath('.//button[@data-sc-edit-toggle]')), 1)
        self.assertEqual(self._fields(card), ['external_notes'])

    # -- AC-3 ------------------------------------------------------------
    def test_report_page_has_no_external_note_for_a_coach(self):
        url = '/my/patient/injury/new?patient_id=%s' % self.player.id
        self._login_coach()
        _text, tree = self._get(url)
        form = tree.xpath('//form[@data-sc-form="injury.new"]')[0]
        self.assertNotIn('external_notes', self._fields(form))
        self.assertIn('diagnosis', self._fields(form))
        self._login_tp()
        _text, tree = self._get(url)
        form = tree.xpath('//form[@data-sc-form="injury.new"]')[0]
        self.assertIn('external_notes', self._fields(form))

    def test_coach_create_ignores_external_note(self):
        self._login_coach()
        inline = self._create(sc_inline='1', diagnosis='Synthetic inline 1675',
                              external_notes='Coach inline note')
        self.assertEqual(len(inline), 1)
        self.assertFalse(inline.external_notes)
        page = self._create(diagnosis='Synthetic page 1675', injury_date='2026-03-03',
                            external_notes='Coach page note')
        self.assertEqual(len(page), 1)
        self.assertFalse(page.external_notes)

    def test_therapist_create_keeps_external_note(self):
        self._login_tp()
        created = self._create(diagnosis='Synthetic tp 1675', injury_date='2026-03-03',
                               parental_consent='yes', external_notes='Therapist note')
        self.assertEqual(len(created), 1)
        self.assertEqual(created.external_notes, 'Therapist note')

    # -- AC-4 ------------------------------------------------------------
    def test_coach_legacy_save_ignores_external_note_in_app(self):
        self._login_coach()
        for extra in ({'partial': '1'}, {'diagnosis': self.injury.diagnosis}):
            with self.subTest(extra=extra):
                self.url_open('/my/injury/save', data={
                    'csrf_token': self._csrf(), 'injury_id': self.injury.id,
                    'external_notes': 'Coach legacy note', **extra,
                }, allow_redirects=False)
                self.injury.invalidate_recordset()
                self.assertEqual(self.injury.external_notes, EXT)

    # -- AC-5 ------------------------------------------------------------
    def test_legacy_coach_report_drops_external_note(self):
        self._switch(False)
        self._login_coach()
        _text, tree = self._get('/my/patient/injury/new?patient_id=%s' % self.player.id)
        self.assertFalse(tree.xpath('//textarea[@name="external_notes"]'))
        self.assertTrue(tree.xpath('//textarea[@name="diagnosis"]'))
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'diagnosis': 'Synthetic legacy 1675', 'injury_date': '2026-03-03',
            'external_notes': 'Coach legacy report'})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn('data-sc-warning="external_notes_readonly"', resp.text)
        created = self.env['sports.patient.injury'].sudo().search(
            [('patient_id', '=', self.player.id), ('diagnosis', '=', 'Synthetic legacy 1675')])
        self.assertEqual(len(created), 1)
        self.assertFalse(created.external_notes)
        # Without an external note: no warning.
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'diagnosis': 'Synthetic legacy 1675 b', 'injury_date': '2026-03-03'})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertNotIn('data-sc-warning', resp.text)

    def test_legacy_coach_edit_form_external_note_read_only(self):
        self._switch(False)
        self._login_coach()
        _text, tree = self._get('/my/injury/edit?injury_id=%s' % self.injury.id)
        area = tree.xpath('//textarea[@name="external_notes"]')[0]
        self.assertEqual(area.get('readonly'), 'readonly')
        self.assertIn(EXT, area.text_content())
        self.assertFalse(tree.xpath('//*[@data-clear-target="external_notes"]'))
        self._login_tp()
        _text, tree = self._get('/my/injury/edit?injury_id=%s' % self.injury.id)
        self.assertIsNone(tree.xpath('//textarea[@name="external_notes"]')[0].get('readonly'))

    def test_legacy_coach_save_drops_external_note_with_a_flash(self):
        self._switch(False)
        self._login_coach()
        for extra in ({'partial': '1'}, {'diagnosis': self.injury.diagnosis}):
            with self.subTest(extra=extra):
                resp = self.url_open('/my/injury/save', data={
                    'csrf_token': self._csrf(), 'injury_id': self.injury.id,
                    'external_notes': 'Coach legacy note', **extra,
                })
                self.assertEqual(resp.status_code, 200, resp.text)
                self.assertIn('warning=external_notes_readonly', resp.url)
                self.assertIn('data-sc-warning="external_notes_readonly"', resp.text)
                self.injury.invalidate_recordset()
                self.assertEqual(self.injury.external_notes, EXT)
        # The read-only textarea posted back as is: saved, no warning.
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id,
            'diagnosis': 'Synthetic coach diagnosis', 'external_notes': EXT,
        })
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertNotIn('warning=', resp.url)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, EXT)

    def test_legacy_therapist_save_keeps_external_note(self):
        self._switch(False)
        self._login_tp()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id, 'partial': '1',
            'external_notes': 'Therapist legacy note'})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertNotIn('warning=', resp.url)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'Therapist legacy note')

    # -- AC-6 ------------------------------------------------------------
    def test_model_refuses_external_notes_from_a_coach(self):
        Injury = self.env['sports.patient.injury']
        with mute_logger('odoo.models'), self.assertRaises(AccessError):
            self.injury.with_user(self.coach).write({'external_notes': 'Coach RPC note'})
        with mute_logger('odoo.models'), self.assertRaises(AccessError):
            Injury.with_user(self.coach).create({
                'patient_id': self.player.id, 'diagnosis': 'Synthetic coach rpc',
                'external_notes': 'Coach RPC note'})
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, EXT)
        # The coach's other writes / creates still go through.
        created = Injury.with_user(self.coach).create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic coach report'})
        self.assertFalse(created.sudo().external_notes)

    def test_model_allows_external_notes_for_therapist_and_superuser(self):
        Injury = self.env['sports.patient.injury']
        self.injury.with_user(self.tp).write({'external_notes': 'Therapist ORM note'})
        self.assertEqual(self.injury.sudo().external_notes, 'Therapist ORM note')
        created = Injury.with_user(self.tp).create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic tp orm',
            'external_notes': 'Therapist ORM create'})
        self.assertEqual(created.sudo().external_notes, 'Therapist ORM create')
        # Superuser (imports, merges, crons) — even on a coach's env.
        self.injury.with_user(self.coach).sudo().write({'external_notes': 'Su note'})
        self.assertEqual(self.injury.sudo().external_notes, 'Su note')
        created = Injury.with_user(self.coach).sudo().create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic su create',
            'external_notes': 'Su create'})
        self.assertEqual(created.external_notes, 'Su create')
        # An internal user (the back end) is not concerned.
        self.injury.write({'external_notes': 'Admin note'})
        self.assertEqual(self.injury.sudo().external_notes, 'Admin note')
