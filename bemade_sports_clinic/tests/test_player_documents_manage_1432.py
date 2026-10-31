"""Task 1432 — player documents: edit + delete (archive) from the portal, for
the uploader and the clinic administrators only. Synthetic fixtures only
(this repository is public).

Use case: a therapist uploaded a document to the wrong player / injury, with
a typo in its name, or by mistake; she fixes or removes it from the player's
Documents tab (or the injury card) without asking an administrator. A
colleague who did not upload it only reads / downloads it. « Delete »
archives the document (a clinic administrator restores it from the
backend) and leaves an internal note on the player.

Acceptance criteria:

* AC-1 The uploader edits (name, category, description, injury link — the
  autosave pencil) a player-level AND an injury-level document; the injury
  link only accepts the player's own injuries (or none).
* AC-2 The uploader deletes a player-level AND an injury-level document: it
  is archived (not unlinked), the user comes back to the page she came from
  with « Document deleted. », and the player gets the internal note
  « Document « name » deleted by user » (no follower notified).
* AC-3 Another therapist (not the uploader) cannot: the edit is refused
  (403) and the delete comes back with « permission denied » (never a 404 /
  500); the record is unchanged. A coach cannot either.
* AC-4 A clinic administrator (not the uploader) can edit and delete.
* AC-5 Buttons: the uploader sees the pencil + « Delete » (with its
  « Delete this document? » confirmation) on the Documents tab and on the
  injury card; another therapist sees the download only.
* AC-6 An archived document disappears from the Documents tab, the injury
  card and the player's document count, and both download routes refuse it.
* AC-7 Backend: the archived document is found with the « Archived » filter
  and restored by setting it active again.
* AC-8 fr_CA (website-aware): the tab's « Modifier » / « Supprimer » labels,
  « Supprimer ce document ? » and the link field render in French.
"""
import json

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


class PlayerDocuments1432Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'SC1432 Other Therapist', 'login': 'sc1432.tp2@example.com',
            'password': 'sc1432-tp2-pass',
            'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id, 'role': 'therapist',
        })
        cls.injury_b = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'SC1432 Second injury',
        })
        cls.injury_foreign = env['sports.patient.injury'].create({
            'patient_id': cls.player_b.id, 'diagnosis': 'SC1432 Other player injury',
        })

    def setUp(self):
        super().setUp()
        self._switch(True)
        Doc = self.env['sports.injury.document']
        common = {'patient_id': self.player.id, 'category': 'other', 'file_content': 'U3ludGhldGlj',
                  'created_by_id': self.tp.id}
        self.doc_player = Doc.create(dict(common, name='SC1432 player doc.pdf',
                                          file_name='SC1432 player doc.pdf'))
        self.doc_injury = Doc.create(dict(common, name='SC1432 injury doc.pdf',
                                          file_name='SC1432 injury doc.pdf',
                                          injury_id=self.injury.id))

    # -- helpers -----------------------------------------------------------
    def _login_tp2(self):
        self.authenticate('sc1432.tp2@example.com', 'sc1432-tp2-pass')

    def _save(self, record, field, value):
        record.invalidate_recordset()
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value, 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(record.write_date)}, allow_redirects=False)

    def _delete(self, doc, return_url=None):
        data = {'csrf_token': self._csrf()}
        if return_url:
            data['return_url'] = return_url
        return self.url_open('/my/injury/document/delete/%s' % doc.id, data=data,
                             allow_redirects=False)

    @staticmethod
    def _alive(doc):
        doc.invalidate_recordset()
        return doc.with_context(active_test=False).exists() and doc.active

    def _tab_url(self):
        return '/my/player?player_id=%s&tab=documents' % self.player.id

    def _tab(self, tree):
        nodes = tree.xpath('//*[@data-sc-tab-panel="documents"]')
        return nodes[0] if nodes else None

    def _tab_item(self, tree, doc):
        rows = self._tab(tree).xpath('.//*[@data-sc-document-id="%s"]' % doc.id)
        return rows[0].getparent() if rows else None


@tagged('post_install', '-at_install')
class TestPlayerDocuments1432(PlayerDocuments1432Common):

    # -- AC-1 ------------------------------------------------------------
    def test_uploader_edits_player_and_injury_docs(self):
        self._login_tp()
        for doc in (self.doc_player, self.doc_injury):
            resp = self._save(doc, 'name', 'SC1432 renamed %s' % doc.id)
            self.assertEqual(resp.status_code, 200, resp.text)
            resp = self._save(doc, 'category', 'prescription')
            self.assertEqual(resp.status_code, 200, resp.text)
            resp = self._save(doc, 'description', 'SC1432 synthetic description')
            self.assertEqual(resp.status_code, 200, resp.text)
            doc.invalidate_recordset()
            self.assertEqual(doc.name, 'SC1432 renamed %s' % doc.id)
            self.assertEqual(doc.category, 'prescription')
            self.assertEqual(doc.description, 'SC1432 synthetic description')
        # Re-link: player-level -> injury B, injury-level -> none.
        self.assertEqual(self._save(self.doc_player, 'injury_id', str(self.injury_b.id)).status_code, 200)
        self.assertEqual(self._save(self.doc_injury, 'injury_id', '').status_code, 200)
        self.doc_player.invalidate_recordset()
        self.doc_injury.invalidate_recordset()
        self.assertEqual(self.doc_player.injury_id, self.injury_b)
        self.assertFalse(self.doc_injury.injury_id)

    def test_injury_link_restricted_to_player(self):
        self._login_tp()
        resp = self._save(self.doc_player, 'injury_id', str(self.injury_foreign.id))
        self.assertIn(resp.status_code, (400, 403))
        self.doc_player.invalidate_recordset()
        self.assertFalse(self.doc_player.injury_id)

    # -- AC-2 ------------------------------------------------------------
    def test_uploader_archives_player_doc_with_note(self):
        Message = self.env['mail.message']
        before = Message.search([('model', '=', 'sports.patient'), ('res_id', '=', self.player.id)])
        self._login_tp()
        back = self._tab_url() + '#documents'
        resp = self._delete(self.doc_player, return_url=back)
        self.assertIn(resp.status_code, (302, 303))
        location = resp.headers['Location']
        self.assertIn('/my/player?player_id=%s' % self.player.id, location)
        self.assertIn('success=document_deleted', location)
        self.assertTrue(self.doc_player.with_context(active_test=False).exists(), 'archived, not unlinked')
        self.assertFalse(self._alive(self.doc_player))
        notes = Message.search([('model', '=', 'sports.patient'), ('res_id', '=', self.player.id)]) - before
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes.subtype_id, self.env.ref('mail.mt_note'))
        self.assertIn('SC1432 player doc.pdf', notes.body)
        self.assertIn(self.tp.name, notes.body)
        self.assertEqual(notes.author_id, self.tp.partner_id)
        self.assertFalse(notes.notified_partner_ids, 'nobody notified')
        # The page says so.
        text, _tree = self._get(location)
        self.assertIn('Document deleted.', text)

    def test_uploader_archives_injury_doc(self):
        self._login_tp()
        resp = self._delete(self.doc_injury)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('success=document_deleted', resp.headers['Location'])
        self.assertFalse(self._alive(self.doc_injury))

    def test_player_level_doc_without_return_url(self):
        """The old route 404'd on a player-level document (no injury)."""
        self._login_tp()
        resp = self._delete(self.doc_player)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('player_id=%s' % self.player.id, resp.headers['Location'])
        self.assertIn('tab=documents', resp.headers['Location'])
        self.assertFalse(self._alive(self.doc_player))

    # -- AC-3 ------------------------------------------------------------
    @mute_logger('odoo.addons.bemade_sports_clinic.controllers.app_shell',
                 'odoo.addons.bemade_sports_clinic.controllers.patient_injury_portal')
    def test_other_therapist_refused(self):
        self._login_tp2()
        for doc in (self.doc_player, self.doc_injury):
            resp = self._save(doc, 'name', 'SC1432 hijacked')
            self.assertEqual(resp.status_code, 403, resp.text)
            resp = self._delete(doc, return_url=self._tab_url())
            self.assertIn(resp.status_code, (302, 303))
            self.assertIn('error=permission_denied', resp.headers['Location'])
            doc.invalidate_recordset()
            self.assertTrue(self._alive(doc))
            self.assertNotEqual(doc.name, 'SC1432 hijacked')

    @mute_logger('odoo.addons.bemade_sports_clinic.controllers.app_shell',
                 'odoo.addons.bemade_sports_clinic.controllers.patient_injury_portal')
    def test_coach_refused(self):
        self._login_coach()
        resp = self._save(self.doc_player, 'name', 'SC1432 coach')
        self.assertEqual(resp.status_code, 403)
        resp = self._delete(self.doc_player, return_url=self._tab_url())
        self.assertIn(resp.status_code, (302, 303, 404))
        self.assertTrue(self._alive(self.doc_player))

    def test_internal_non_admin_therapist_refused(self):
        self._login_itp()
        resp = self._delete(self.doc_player, return_url=self._tab_url())
        self.assertIn('error=permission_denied', resp.headers['Location'])
        self.assertTrue(self._alive(self.doc_player))

    # -- AC-4 ------------------------------------------------------------
    def test_clinic_admin_manages(self):
        self._login_cadmin()
        self.assertEqual(self._save(self.doc_injury, 'name', 'SC1432 by admin').status_code, 200)
        self.doc_injury.invalidate_recordset()
        self.assertEqual(self.doc_injury.name, 'SC1432 by admin')
        resp = self._delete(self.doc_player, return_url=self._tab_url())
        self.assertIn('success=document_deleted', resp.headers['Location'])
        self.assertFalse(self._alive(self.doc_player))

    # -- AC-5 ------------------------------------------------------------
    def test_buttons_for_uploader(self):
        self._login_tp()
        _text, tree = self._get(self._tab_url())
        item = self._tab_item(tree, self.doc_player)
        self.assertEqual(item.get('data-sc-edit-card'), 'player-document-%s' % self.doc_player.id)
        self.assertTrue(item.xpath('.//button[@data-sc-action="documents.edit"]'))
        self.assertTrue(item.xpath('.//button[@data-sc-action="documents.delete"]'))
        props = {json.loads(p)['field'] for p in item.xpath('.//owl-component/@props')}
        self.assertEqual(props, {'name', 'category', 'description', 'injury_id'})
        injury_prop = [json.loads(p) for p in item.xpath('.//owl-component/@props')
                       if json.loads(p)['field'] == 'injury_id'][0]
        keys = [o[0] for o in injury_prop['options']]
        self.assertEqual(keys[0], '')
        self.assertIn(str(self.injury_b.id), keys)
        self.assertNotIn(str(self.injury_foreign.id), keys)
        form = tree.xpath('//dialog[@id="sc_delete_player_document_%s"]//form' % self.doc_player.id)[0]
        self.assertEqual(form.get('action'), '/my/injury/document/delete/%s' % self.doc_player.id)
        self.assertIn('documents', form.xpath('.//input[@name="return_url"]/@value')[0])
        # The injury card too.
        card = tree.xpath('//*[@data-sc-edit-card="document-%s"]' % self.doc_injury.id)
        self.assertTrue(card)
        self.assertTrue(tree.xpath('//dialog[@id="sc_delete_document_%s"]' % self.doc_injury.id))

    def test_buttons_hidden_for_other_therapist(self):
        self._login_tp2()
        _text, tree = self._get(self._tab_url())
        for doc in (self.doc_player, self.doc_injury):
            item = self._tab_item(tree, doc)
            self.assertIsNotNone(item, 'listed (read-only)')
            self.assertFalse(item.get('data-sc-edit-card'))
            self.assertFalse(item.xpath('.//button[@data-sc-action="documents.edit"]'))
            self.assertFalse(item.xpath('.//button[@data-sc-action="documents.delete"]'))
            self.assertTrue(item.xpath('.//a[@data-sc-action="documents.download"]'))
        self.assertFalse(tree.xpath('//*[@data-sc-edit-card="document-%s"]' % self.doc_injury.id))
        self.assertFalse(tree.xpath('//dialog[@id="sc_delete_document_%s"]' % self.doc_injury.id))
        self.assertFalse(tree.xpath('//dialog[starts-with(@id, "sc_delete_player_document_")]'))

    # -- AC-6 ------------------------------------------------------------
    def test_archived_hidden_everywhere(self):
        count_before = self.player.document_count
        self.doc_player.sudo()._sc_portal_archive(self.tp)
        self.doc_injury.sudo()._sc_portal_archive(self.tp)
        self.player.invalidate_recordset()
        self.injury.invalidate_recordset()
        self.assertEqual(self.player.document_count, count_before - 2)
        self.assertEqual(self.injury.document_count, 0)
        self._login_tp()
        _text, tree = self._get(self._tab_url())
        self.assertFalse(tree.xpath('//*[@data-sc-document-id="%s"]' % self.doc_player.id))
        self.assertFalse(tree.xpath('//*[@data-sc-document-id="%s"]' % self.doc_injury.id))
        for url in ('/my/patient/document/download/%s' % self.doc_player.id,
                    '/my/injury/document/download/%s' % self.doc_injury.id,
                    '/my/patient/document/download/%s' % self.doc_injury.id):
            self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 404, url)
        # A save on an archived document is refused too.
        self.assertNotEqual(self._save(self.doc_player, 'name', 'SC1432 ghost').status_code, 200)

    def test_live_download_still_works(self):
        self._login_tp2()
        resp = self.url_open('/my/patient/document/download/%s' % self.doc_player.id)
        self.assertEqual(resp.status_code, 200)

    # -- AC-7 ------------------------------------------------------------
    def test_backend_archived_filter_and_restore(self):
        self.doc_player.sudo()._sc_portal_archive(self.tp)
        Doc = self.env['sports.injury.document']
        search = self.env.ref('bemade_sports_clinic.view_injury_document_search')
        self.assertIn('name="inactive"', search.arch_db)
        archived = Doc.search([('active', '=', False), ('patient_id', '=', self.player.id)])
        self.assertEqual(archived, self.doc_player)
        archived.active = True
        self.assertIn(self.doc_player, Doc.search([('patient_id', '=', self.player.id)]))

    def test_undo_create_counts_archived(self):
        """An archived document still blocks an injury's « undo » (the
        unlink would cascade onto it)."""
        self.doc_injury.sudo()._sc_portal_archive(self.tp)
        self.assertTrue(self.injury.with_context(active_test=False).document_ids)


@tagged('post_install', '-at_install')
class TestPlayerDocumentsFr1432(PlayerDocuments1432Common):
    """AC-8 — fr_CA, website-aware."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.tp.write({'lang': 'fr_CA'})

    def test_french(self):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get(self._tab_url())
        item = self._tab_item(tree, self.doc_player)
        self.assertEqual(item.xpath('.//button[@data-sc-action="documents.delete"]/@title'), ['Supprimer'])
        self.assertEqual(item.xpath('.//button[@data-sc-action="documents.edit"]/@title'), ['Modifier'])
        dialog = tree.xpath('//dialog[@id="sc_delete_player_document_%s"]' % self.doc_player.id)[0]
        self.assertIn('Supprimer ce document ?', ' '.join(dialog.text_content().split()))
        labels = {json.loads(p)['field']: json.loads(p)['label'] for p in item.xpath('.//owl-component/@props')}
        self.assertEqual(labels['injury_id'], 'Lien vers la blessure (optionnel)')
        options = [json.loads(p) for p in item.xpath('.//owl-component/@props')
                   if json.loads(p)['field'] == 'injury_id'][0]['options']
        self.assertEqual(options[0][1], '-- Aucune --')
