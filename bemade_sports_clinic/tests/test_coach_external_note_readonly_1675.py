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
* AC-5 Legacy portal pages (switch off) keep today's behaviour: a coach's
  report still records its external note.
"""
import json

from odoo import fields
from odoo.tests import tagged

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
    def test_legacy_portal_unchanged(self):
        self._switch(False)
        self._login_coach()
        created = self._create(diagnosis='Synthetic legacy 1675', injury_date='2026-03-03',
                               external_notes='Coach legacy report')
        self.assertEqual(len(created), 1)
        self.assertEqual(created.external_notes, 'Coach legacy report')
