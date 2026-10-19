"""Task 1616 — the injury card in three sections (Détails · Notes ·
Documents), one pencil per group; the injury page and its documents page
collapse into the card. Synthetic fixtures only (this repository is public).

Use case: a therapist (or a coach) expands an injury on the player page or
in the clinic dossier and finds everything the former injury page offered —
the details, the notes with their history, the documents (several added at
once) and « Delete » — without leaving the list; an old injury-page link
lands on that open card.

Acceptance criteria:

* AC-1 The open card holds three sections in this order — Details
  (``injury.details``), Notes (``injury.notes``), Documents
  (``injury.documents``) — then « Delete » (therapists) and « Done »; no
  « Treatment notes, documents and history » link, no treatment note.
* AC-2 One pencil per group: the Details edit view holds the injury fields
  only (diagnosis, date, status, predicted / resolution dates, consent,
  visibility), the Notes edit view the two notes only (replace editors with
  their « last note » stamp and scoped history sheets); the combined
  « History » sheet is reachable from the Notes head.
* AC-3 Gates follow the former page: a coach gets Details (the date of a
  verified injury), the external notes and the documents
  list (download) — no status, visibility, consent, internal notes, upload,
  document edit / delete or injury delete.
* AC-4 Read fragments (task 1611) stay stable: the card item, ``summary``
  (with the #1604 quick button), ``read`` (Details) — plus ``notes`` (Notes
  read view) and each document's ``row``; a document save refreshes it.
* AC-5 Documents: the card lists its injury's documents (download, delete
  with confirm coming back to the open card); « Add » opens a sheet whose
  form takes SEVERAL files (``multiple``), one category / description, and
  comes back to the card.
* AC-6 Multi-file upload: two files -> two documents with the category /
  description, back on the card with « 2 documents uploaded. »; one file
  over 10 MB -> NONE saved and the message names it; an injury of another
  player is refused.
* AC-7 Each document can be re-filed afterwards (name / category /
  description autosave, therapists only; a coach gets 403).
* AC-8 « Delete » (confirm sheet) deletes the injury and comes back to the
  list the card was in (player Injuries tab / clinic dossier).
* AC-9 Redirects: /my/injury/edit and /my/injury/documents (shell on) land
  on the open card — player page with the team / clinic context, or the
  clinic dossier when that clinic lists the injury (a resolved one falls
  back to the player page); the retired note-history page too; a
  ``success`` message is carried along. Switch off: today's pages.
* AC-10 Links into the app point at the card: the activity's related
  injury link, the Notes tab's linked-injury link.
* AC-11 fr_CA: « Détails », « Notes », « Documents », « Ajouter des
  documents », the multi-upload message.
"""
from urllib.parse import parse_qs, unquote, urlparse

from lxml import html as lxml_html

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon
from odoo.addons.bemade_sports_clinic.tests.test_clinic_dossier_inline_1590 import ClinicDossier1590Common

ELEVEN_MB = 11 * 1024 * 1024


class InjuryCard1616Mixin:
    """Helpers shared by the player-page and dossier classes."""

    def _player_url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id

    def _card(self, tree, injury=None, prefix='injury-'):
        injury = injury or self.injury
        nodes = tree.xpath('//details[@id="%s%s"]' % (prefix, injury.id))
        self.assertEqual(len(nodes), 1, 'one card for injury %s' % injury.id)
        return nodes[0]

    @staticmethod
    def _sections(card):
        return card.xpath('.//section[contains(@class, "o_sc_injury_section")]/@data-sc-section')

    @staticmethod
    def _fields(scope):
        import json
        return [json.loads(node.get('props')).get('field')
                for node in scope.xpath('.//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]')]

    def _doc(self, name='Synthetic scan.pdf', injury=None, **extra):
        return self.env['sports.injury.document'].create(dict({
            'patient_id': self.player.id, 'injury_id': (injury or self.injury).id,
            'name': name, 'file_name': name, 'category': 'other',
            'file_content': 'U3ludGhldGlj',  # base64 of « Synthetic »
        }, **extra))

    def _location(self, resp):
        self.assertIn(resp.status_code, (301, 302, 303), resp.text[:300])
        parts = urlparse(resp.headers['Location'])
        return parts.path, parse_qs(parts.query), parts.fragment

    def _upload(self, files, injury=None, **data):
        payload = {
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'injury_id': (injury or self.injury).id,
            'return_url': '%s&injury=%s#injury-%s' % (self._player_url(), self.injury.id, self.injury.id),
        }
        payload.update(data)
        return self.url_open('/my/patient/document/upload', data=payload, allow_redirects=False,
                             files=[('attachment', (name, content, 'application/pdf'))
                                    for name, content in files])


@tagged('post_install', '-at_install')
class TestInjuryCard1616(InjuryCard1616Mixin, FragmentsMixin, AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- AC-1 ------------------------------------------------------------
    def test_three_sections_then_delete_and_done(self):
        self.env['sports.treatment.note'].create({
            'patient_id': self.player.id, 'injury_id': self.injury.id,
            'note': 'Synthetic treatment note 1616', 'user_id': self.tp.id,
        })
        self._login_tp()
        text, tree = self._get(self._player_url())
        card = self._card(tree)
        self.assertEqual(self._sections(card), ['injury.details', 'injury.notes', 'injury.documents'])
        self.assertFalse(card.xpath('.//a[contains(@href, "/my/injury/edit")]'))
        self.assertFalse(card.xpath('.//*[@data-sc-action="injury.open"]'))
        self.assertNotIn('Synthetic treatment note 1616', lxml_html.tostring(card, encoding='unicode'))
        actions = card.xpath('.//div[contains(@class, "o_sc_injury_card_actions")]//button/@data-sc-action')
        self.assertEqual(actions, ['injury.delete', 'injury.done'])
        sheet = card.xpath('.//dialog[@id="sc_delete_injury_sheet_%s"]//form' % self.injury.id)[0]
        self.assertEqual(sheet.get('action'), '/my/injury/delete')
        hidden = dict(zip(sheet.xpath('.//input[@type="hidden"]/@name'),
                          sheet.xpath('.//input[@type="hidden"]/@value')))
        self.assertEqual(hidden['injury_id'], str(self.injury.id))
        self.assertEqual(hidden['return_url'], self._player_url())
        self.assertTrue(hidden['csrf_token'])

    # -- AC-2 ------------------------------------------------------------
    def test_one_pencil_per_group(self):
        self._login_tp()
        _text, tree = self._get(self._player_url())
        card = self._card(tree)
        details = card.xpath('.//section[@data-sc-edit-card="injury-details"]')[0]
        notes = card.xpath('.//section[@data-sc-edit-card="injury-notes"]')[0]
        self.assertEqual(len(details.xpath('.//button[@data-sc-edit-toggle]')), 1)
        self.assertEqual(len(notes.xpath('.//button[@data-sc-edit-toggle]')), 1)
        self.assertEqual(self._fields(details.xpath('.//*[@data-sc-edit-view="edit"]')[0]), [
            'diagnosis', 'sc_injury_date', 'stage', 'predicted_resolution_date',
            'resolution_date', 'parental_consent', 'hidden_from_coaches'])
        self.assertEqual(self._fields(notes.xpath('.//*[@data-sc-edit-view="edit"]')[0]),
                         ['external_notes', 'internal_notes'])
        import json
        ext = json.loads(notes.xpath('.//owl-component')[0].get('props'))
        self.assertTrue(ext['replace'])
        self.assertEqual(ext['historySheet'], 'sc_note_history_sheet_%s_external' % self.injury.id)
        # The combined « History » sheet from the Notes head.
        self.assertTrue(notes.xpath('.//div[contains(@class, "o_sc_edit_card_head")]'
                                    '//button[@data-sc-sheet-open="sc_note_history_sheet_%s"]' % self.injury.id))
        lazy = notes.xpath('.//dialog[@id="sc_note_history_sheet_%s"]/@data-sc-lazy-url' % self.injury.id)
        self.assertEqual(lazy, ['/my/injury/%s/notes/history/fragment' % self.injury.id])

    def test_stamp_under_the_notes_on_the_player_page(self):
        self._login_tp()
        self._saved(self.injury, 'external_notes', 'Synthetic external 1616')
        _text, tree = self._get(self._player_url())
        import json
        notes = self._card(tree).xpath('.//section[@data-sc-edit-card="injury-notes"]')[0]
        ext = json.loads(notes.xpath('.//owl-component')[0].get('props'))
        self.assertTrue(ext.get('hint'), 'the « last note » stamp is shown on the player page too')

    # -- AC-3 ------------------------------------------------------------
    def test_coach_card(self):
        self._doc()
        self._login_coach()
        _text, tree = self._get(self._player_url())
        card = self._card(tree)
        self.assertEqual(self._sections(card), ['injury.details', 'injury.notes', 'injury.documents'])
        details = card.xpath('.//section[@data-sc-edit-card="injury-details"]')[0]
        self.assertEqual(self._fields(details), ['sc_injury_date'])  # active: no rewording
        notes = card.xpath('.//section[@data-sc-edit-card="injury-notes"]')[0]
        self.assertEqual(self._fields(notes), ['external_notes'])
        self.assertFalse(notes.xpath('.//dialog[contains(@id, "_internal")]'))
        docs = card.xpath('.//section[@data-sc-section="injury.documents"]')[0]
        self.assertEqual(len(docs.xpath('.//*[contains(@class, "o_sc_doc_row")]')), 1)
        self.assertTrue(docs.xpath('.//a[@data-sc-action="documents.download"]'))
        for action in ('injury.documents.add', 'documents.delete', 'documents.edit'):
            self.assertFalse(docs.xpath('.//*[@data-sc-action="%s"]' % action), action)
        self.assertFalse(docs.xpath('.//form'))
        self.assertFalse(card.xpath('.//*[@data-sc-action="injury.delete"]'))
        self.assertTrue(card.xpath('.//*[@data-sc-action="injury.done"]'))

    # -- AC-4 ------------------------------------------------------------
    def test_fragments(self):
        doc = self._doc()
        self._login_tp()
        _text, tree = self._get(self._player_url())
        card = self._card(tree)
        key = 'sports.patient.injury:%s:' % self.injury.id
        self.assertEqual(card.get('data-sc-fragment-item'), key + 'card')
        summary = card.xpath('./summary')[0]
        self.assertEqual(summary.get('data-sc-fragment'), key + 'summary')
        self.assertTrue(summary.xpath('.//span[contains(@class, "o_sc_row_trailing")]/button[@data-sc-injury-quick]'))
        read = card.xpath('.//section[@data-sc-edit-card="injury-details"]/dl[@data-sc-edit-view="read"]')[0]
        self.assertEqual(read.get('data-sc-fragment'), key + 'read')
        notes = card.xpath('.//section[@data-sc-edit-card="injury-notes"]/dl[@data-sc-edit-view="read"]')[0]
        self.assertEqual(notes.get('data-sc-fragment'), key + 'notes')
        # A notes save refreshes the Notes read view (the injury's '*').
        payload = self._saved(self.injury, 'external_notes', 'Synthetic external 1616')
        self.assertRefreshes(payload, key + 'notes')
        self.assertIn('Synthetic external 1616', self._text(self._fragment(self._player_url(), key + 'notes')))
        self.assertFragmentMatchesPage(self._player_url(), key + 'notes')
        # A document save refreshes its row.
        row_key = 'sports.injury.document:%s:row' % doc.id
        payload = self._saved(doc, 'name', 'Synthetic X-ray report')
        self.assertRefreshes(payload, row_key)
        self.assertIn('Synthetic X-ray report', self._text(self._fragment(self._player_url(), row_key)))

    # -- AC-5 ------------------------------------------------------------
    def test_documents_section(self):
        doc = self._doc(description='Synthetic description')
        other = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic wrist'})
        self._doc('Synthetic other.pdf', injury=other)
        self._login_tp()
        _text, tree = self._get(self._player_url())
        docs = self._card(tree).xpath('.//section[@data-sc-section="injury.documents"]')[0]
        rows = docs.xpath('.//*[contains(@class, "o_sc_doc_row")]')
        self.assertEqual([r.get('data-sc-document-id') for r in rows], [str(doc.id)])
        self.assertEqual(docs.xpath('.//a[@data-sc-action="documents.download"]/@href'),
                         ['/my/injury/document/download/%s' % doc.id])
        card_url = '%s&injury=%s#injury-%s' % (self._player_url(), self.injury.id, self.injury.id)
        delete = docs.xpath('.//dialog[@id="sc_delete_document_%s"]//form' % doc.id)[0]
        self.assertEqual(delete.get('action'), '/my/injury/document/delete/%s' % doc.id)
        self.assertEqual(delete.xpath('.//input[@name="return_url"]/@value'), [card_url])
        # « Add »: a sheet with ONE multi-file form coming back to the card.
        self.assertTrue(docs.xpath('.//button[@data-sc-action="injury.documents.add"]'
                                   '[@data-sc-sheet-open="sc_injury_%s_documents_add"]' % self.injury.id))
        form = docs.xpath('.//dialog[@id="sc_injury_%s_documents_add"]//form' % self.injury.id)[0]
        self.assertEqual(form.get('action'), '/my/patient/document/upload')
        self.assertEqual(form.get('enctype'), 'multipart/form-data')
        self.assertTrue(form.xpath('.//input[@type="file"][@name="attachment"][@multiple]'))
        self.assertEqual(form.xpath('.//input[@name="return_url"]/@value'), [card_url])
        self.assertEqual(form.xpath('.//input[@name="injury_id"]/@value'), [str(self.injury.id)])
        self.assertNotIn('xray', form.xpath('.//select[@name="category"]/option/@value'))
        # The other injury's card lists its own document only.
        other_docs = self._card(tree, other).xpath('.//*[contains(@class, "o_sc_doc_row")]/@data-sc-document-id')
        self.assertEqual(len(other_docs), 1)
        self.assertNotEqual(other_docs[0], str(doc.id))

    def test_documents_batch_loaded(self):
        for index in range(3):
            injury = self.env['sports.patient.injury'].create({
                'patient_id': self.player.id, 'diagnosis': 'Synthetic %s' % index})
            self._doc('Synthetic %s.pdf' % index, injury=injury)
        self._login_tp()
        Document = self.env.registry['sports.injury.document']
        calls = []
        original = Document._search

        def counting(this, *args, **kwargs):
            calls.append(1)
            return original(this, *args, **kwargs)

        from unittest.mock import patch
        with patch.object(Document, '_search', counting):
            self._get(self._player_url())
        # The Documents tab's list + the cards' batch (never one per card).
        self.assertLessEqual(len(calls), 3)

    # -- AC-6 ------------------------------------------------------------
    def test_upload_several_files(self):
        self._login_tp()
        resp = self._upload([('Synthetic a.pdf', b'aaa'), ('Synthetic b.pdf', b'bbb')],
                            category='medical_imaging', description='Synthetic batch')
        path, query, frag = self._location(resp)
        self.assertEqual(path, '/my/player')
        self.assertEqual(query['injury'], [str(self.injury.id)])
        self.assertEqual(query['success'], ['documents_uploaded'])
        self.assertEqual(query['count'], ['2'])
        self.assertEqual(frag, 'injury-%s' % self.injury.id)
        docs = self.env['sports.injury.document'].search([('injury_id', '=', self.injury.id)])
        self.assertEqual(sorted(docs.mapped('name')), ['Synthetic a.pdf', 'Synthetic b.pdf'])
        self.assertEqual(set(docs.mapped('category')), {'medical_imaging'})
        self.assertEqual(set(docs.mapped('description')), {'Synthetic batch'})
        self.assertEqual(set(docs.mapped('created_by_id')), {self.tp})
        text, tree = self._get(resp.headers['Location'].split('#')[0])
        self.assertIn('2 documents uploaded.', text)
        self.assertEqual(self._card(tree).get('open'), 'open')

    def test_upload_one_file_too_large_saves_none(self):
        self._login_tp()
        resp = self._upload([('Synthetic small.pdf', b'small'), ('Synthetic big.pdf', b'x' * ELEVEN_MB)])
        _path, query, _frag = self._location(resp)
        self.assertEqual(query['error'], ['file_too_large'])
        self.assertEqual(unquote(query['error_files'][0]), 'Synthetic big.pdf')
        self.assertFalse(self.env['sports.injury.document'].search([('injury_id', '=', self.injury.id)]))
        text, _tree = self._get(resp.headers['Location'].split('#')[0])
        self.assertIn('Nothing was uploaded: these files are over 10 MB: Synthetic big.pdf', text)

    def test_upload_refuses_another_players_injury(self):
        other = self.env['sports.patient.injury'].create({
            'patient_id': self.player_b.id, 'diagnosis': 'Synthetic foreign'})
        self._login_tp()
        resp = self._upload([('Synthetic a.pdf', b'aaa')], injury=other)
        _path, query, _frag = self._location(resp)
        self.assertEqual(query['error'], ['invalid_injury'])
        self.assertFalse(self.env['sports.injury.document'].search([('injury_id', '=', other.id)]))

    def test_single_upload_keeps_its_name(self):
        self._login_tp()
        resp = self._upload([('Synthetic a.pdf', b'aaa')], document_name='Synthetic named')
        _path, query, _frag = self._location(resp)
        self.assertEqual(query['success'], ['document_uploaded'])
        self.assertEqual(self.env['sports.injury.document'].search(
            [('injury_id', '=', self.injury.id)]).name, 'Synthetic named')

    # -- AC-7 ------------------------------------------------------------
    def test_document_refiled_afterwards(self):
        doc = self._doc(category='xray')
        self._login_tp()
        _text, tree = self._get(self._player_url())
        item = self._card(tree).xpath('.//*[@data-sc-edit-card="document-%s"]' % doc.id)[0]
        self.assertEqual(self._fields(item), ['name', 'category', 'description'])
        import json
        category = [json.loads(n.get('props')) for n in item.xpath('.//owl-component')
                    if json.loads(n.get('props'))['field'] == 'category'][0]
        self.assertEqual(category['value'], 'medical_imaging')  # the legacy key reads as today's
        payload = self._saved(doc, 'category', 'prescription')
        self.assertTrue(payload['ok'])
        self._saved(doc, 'description', 'Synthetic refiled')
        self.assertEqual((doc.category, doc.description), ('prescription', 'Synthetic refiled'))

    @mute_logger('odoo.http')
    def test_coach_cannot_refile(self):
        doc = self._doc()
        self._login_coach()
        resp = self.url_open('/my/app/save/sports.injury.document/%s' % doc.id, data={
            'csrf_token': self._csrf(), 'field': 'name', 'value': 'Synthetic coach',
            'write_date': str(doc.write_date)})
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(doc.name, 'Synthetic scan.pdf')

    def test_delete_document_back_to_the_card(self):
        doc = self._doc()
        self._login_tp()
        card_url = '%s&injury=%s#injury-%s' % (self._player_url(), self.injury.id, self.injury.id)
        resp = self.url_open('/my/injury/document/delete/%s' % doc.id, data={
            'csrf_token': self._csrf(), 'return_url': card_url}, allow_redirects=False)
        path, query, frag = self._location(resp)
        self.assertEqual((path, query['injury'], query['success'], frag),
                         ('/my/player', [str(self.injury.id)], ['document_deleted'], 'injury-%s' % self.injury.id))
        self.assertFalse(doc.exists())

    # -- AC-8 ------------------------------------------------------------
    def test_delete_injury_back_to_the_list(self):
        self._login_tp()
        resp = self.url_open('/my/injury/delete', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id,
            'return_url': self._player_url(), 'sc_card': '1'}, allow_redirects=False)
        path, query, _frag = self._location(resp)
        self.assertEqual((path, query['tab'], query['success']), ('/my/player', ['injuries'], ['injury_deleted']))
        self.assertFalse(self.injury.exists())

    # -- AC-9 ------------------------------------------------------------
    def test_injury_page_redirects_to_the_card(self):
        self._login_tp()
        for url in ('/my/injury/edit?injury_id=%s&team_id=%s&success=injury_updated',
                    '/my/injury/documents?injury_id=%s&team_id=%s&success=injury_updated'):
            resp = self.url_open(url % (self.injury.id, self.team_a.id), allow_redirects=False)
            path, query, frag = self._location(resp)
            self.assertEqual(path, '/my/player', url)
            self.assertEqual(query['player_id'], [str(self.player.id)])
            self.assertEqual(query['team_id'], [str(self.team_a.id)])
            self.assertEqual(query['tab'], ['injuries'])
            self.assertEqual(query['injury'], [str(self.injury.id)])
            self.assertEqual(query['success'], ['injury_updated'])
            self.assertEqual(frag, 'injury-%s' % self.injury.id)
        # The landing renders the card open, with the message.
        text, tree = self._get('/my/player?player_id=%s&tab=injuries&injury=%s&success=injury_updated'
                               % (self.player.id, self.injury.id))
        self.assertEqual(self._card(tree).get('open'), 'open')
        self.assertIn('Injury updated.', text)

    def test_note_history_page_redirects_to_the_card(self):
        self._login_coach()
        resp = self.url_open('/my/injury/%s/notes/history' % self.injury.id, allow_redirects=False)
        path, query, frag = self._location(resp)
        self.assertEqual((path, query['injury'], frag),
                         ('/my/player', [str(self.injury.id)], 'injury-%s' % self.injury.id))

    def test_coach_never_redirected_to_a_hidden_injury(self):
        hidden = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Hidden synthetic', 'hidden_from_coaches': True})
        self._login_coach()
        with mute_logger('odoo.http'):
            resp = self.url_open('/my/injury/edit?injury_id=%s' % hidden.id, allow_redirects=False)
        self.assertNotIn('injury=%s' % hidden.id, resp.headers.get('Location', ''))

    def test_switch_off_keeps_the_legacy_pages(self):
        self._switch(False)
        self._login_tp()
        for url in ('/my/injury/edit?injury_id=%s', '/my/injury/documents?injury_id=%s'):
            resp = self.url_open(url % self.injury.id, allow_redirects=False)
            self.assertEqual(resp.status_code, 200, url)
            self.assertIsNone(self._shell(lxml_html.fromstring(resp.text)))

    # -- AC-10 -----------------------------------------------------------
    def test_activity_related_link_opens_the_card(self):
        self._login_tp()
        text, tree = self._get('/my/activity/%s' % self.act_injury.id)
        hrefs = tree.xpath('//a[contains(@href, "injury=%s")]/@href' % self.injury.id)
        self.assertTrue(hrefs, 'the related injury links to its card')
        self.assertTrue(all('tab=injuries' in href for href in hrefs))
        self.assertNotIn('/my/injury/edit', text)

    def test_notes_tab_links_to_the_card(self):
        self.env['sports.treatment.note'].create({
            'patient_id': self.player.id, 'injury_id': self.injury.id,
            'note': 'Synthetic linked note', 'user_id': self.tp.id,
        })
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=notes' % self.player.id)
        hrefs = tree.xpath('//section[@data-sc-tab-panel="notes"]//a[contains(@href, "injury=%s")]/@href'
                           % self.injury.id)
        self.assertTrue(hrefs)
        self.assertTrue(all(href.endswith('#injury-%s' % self.injury.id) for href in hrefs))
        self.assertFalse(tree.xpath('//a[contains(@href, "/my/injury/edit")]'))


@tagged('post_install', '-at_install')
class TestInjuryCardDossier1616(InjuryCard1616Mixin, ClinicDossier1590Common):

    def test_dossier_card_sections(self):
        doc = self._doc()
        self._login_tp()
        _text, tree = self._get(self._dossier_url())
        card = self._card(tree, prefix='clinic-injury-')
        self.assertEqual(self._sections(card), ['injury.details', 'injury.notes', 'injury.documents'])
        card_url = '%s&injury=%s#clinic-injury-%s' % (self._dossier_url(), self.injury.id, self.injury.id)
        form = card.xpath('.//dialog[@id="sc_injury_%s_documents_add"]//form' % self.injury.id)[0]
        self.assertEqual(form.xpath('.//input[@name="return_url"]/@value'), [card_url])
        delete = card.xpath('.//dialog[@id="sc_delete_document_%s"]//form' % doc.id)[0]
        self.assertEqual(delete.xpath('.//input[@name="return_url"]/@value'), [card_url])
        sheet = card.xpath('.//dialog[@id="sc_delete_injury_sheet_%s"]//form' % self.injury.id)[0]
        self.assertEqual(sheet.xpath('.//input[@name="return_url"]/@value'), [self._dossier_url()])

    def test_redirect_to_the_dossier_card(self):
        self._login_tp()
        resp = self.url_open('/my/injury/edit?injury_id=%s&clinic_id=%s' % (self.injury.id, self.clinic.id),
                             allow_redirects=False)
        path, query, frag = self._location(resp)
        self.assertEqual(path, '/my/clinic/%s' % self.clinic.id)
        self.assertEqual((query['patient'], query['tab'], query['injury']),
                         ([str(self.player.id)], ['dossier'], [str(self.injury.id)]))
        self.assertEqual(frag, 'clinic-injury-%s' % self.injury.id)
        _text, tree = self._get('%s?%s' % (path, urlparse(resp.headers['Location']).query))
        self.assertEqual(self._card(tree, prefix='clinic-injury-').get('open'), 'open')
        # A resolved injury is not in the dossier: the player page (clinic kept).
        self.injury.with_context(mail_notrack=True).write({'stage': 'resolved'})
        resp = self.url_open('/my/injury/edit?injury_id=%s&clinic_id=%s' % (self.injury.id, self.clinic.id),
                             allow_redirects=False)
        path, query, frag = self._location(resp)
        self.assertEqual((path, query['clinic_id'], frag),
                         ('/my/player', [str(self.clinic.id)], 'injury-%s' % self.injury.id))

    def test_delete_injury_back_to_the_dossier(self):
        self._login_tp()
        resp = self.url_open('/my/injury/delete', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id, 'clinic_id': self.clinic.id,
            'return_url': self._dossier_url(), 'sc_card': '1'}, allow_redirects=False)
        path, query, _frag = self._location(resp)
        self.assertEqual((path, query['success']), ('/my/clinic/%s' % self.clinic.id, ['injury_deleted']))
        text, _tree = self._get(resp.headers['Location'])
        self.assertIn('Injury deleted.', text)


@tagged('post_install', '-at_install')
class TestInjuryCardI18n1616(InjuryCard1616Mixin, TestAppShellI18n1538):
    """fr_CA by render (website-aware: fr_CA on every website + the
    ``frontend_lang`` cookie)."""

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_card_in_french(self):
        self._login_tp()
        text = self._fr(self._player_url()).replace('&#39;', "'")
        for term in ('Détails', 'Notes', 'Documents', 'Ajouter des documents',
                     'Choisissez des fichiers ou déposez-les ici',
                     'Plusieurs fichiers à la fois — 10 Mo maximum chacun',
                     'Aucun document téléchargé'):
            self.assertIn(term, text, term)

    def test_upload_messages_in_french(self):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        text = self._fr(self._player_url() + '&success=documents_uploaded&count=3')
        self.assertIn('3 documents téléversés.', text)
        text = self._fr(self._player_url() + '&error=file_too_large&error_files=Synthetic%20big.pdf')
        self.assertIn('Rien n&#39;a été téléversé', text.replace("'", '&#39;'))
