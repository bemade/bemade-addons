"""Task 1669 — player cards drop « Dernière consultation » (it stays in the
player file); the injury card's Notes read view shows each note's
« Dernière note le … par … » stamp. Synthetic fixtures only.

Acceptance criteria:

* AC-1 The shared player-card detail head (recent-changes detail, row
  detail) has no « Last consultation » line; the player file's Infos still
  shows it.
* AC-2 The injury card's Notes read view (``data-sc-edit-view="read"``)
  carries, under each note, its stamp as an ``o_sc_meta`` line
  (``data-sc-note-stamp="external" / "internal"``): a therapist sees both,
  a coach only the external one, nobody sees one when the note has no
  history.
* AC-3 fr_CA: the read stamp reads « Dernière note le … par … ».
* AC-4 Browser (tour ``sc_1669_note_stamp``, laptop): saving a new external
  note refreshes the read view's stamp in place (no reload).

The real iPhone rendering stays UNVERIFIED until /dev-review.
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _text(node):
    return ' '.join(node.text_content().split())


class Stamps1669Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.write({'last_consultation_date': '2026-02-01', 'match_status': 'no',
                          'practice_status': 'no'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _card_url(self, injury=None):
        return '/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, (injury or self.injury).id)

    def _notes_read(self, tree, injury=None):
        injury = injury or self.injury
        # Task 1675: the Notes section holds one card per note.
        nodes = tree.xpath('//details[@id="injury-%s"]//section[@data-sc-section="injury.notes"]' % injury.id)
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    def _write_notes(self):
        self.injury.with_user(self.tp).with_context(mail_notrack=True).write({
            'external_notes': 'Synthetic external 1669',
            'internal_notes': 'Synthetic internal 1669',
        })
        self.injury.invalidate_recordset()


@tagged('post_install', '-at_install')
class TestCardNoteStamps1669(Stamps1669Common):

    # -- AC-1 --------------------------------------------------------------
    def test_cards_drop_last_consultation(self):
        self._login_tp()
        for url in ('/my/player/%s/row-detail' % self.player.id,
                    '/my/player/%s/recent-changes?detail=1' % self.player.id):
            resp = self.url_open(url)
            self.assertEqual(resp.status_code, 200, url)
            body = _text(lxml_html.fromstring(resp.text))
            self.assertNotIn('Last consultation', body, url)
            self.assertNotIn('fa-stethoscope', resp.text, url)

    def test_player_file_keeps_last_consultation(self):
        self._login_tp()
        text, _tree = self._get('/my/player?player_id=%s&tab=info' % self.player.id)
        self.assertIn('Last consultation', text)

    # -- AC-2 --------------------------------------------------------------
    def test_therapist_sees_both_stamps(self):
        self._write_notes()
        self._login_tp()
        _text_, tree = self._get(self._card_url())
        read = self._notes_read(tree)
        ext = read.xpath('.//*[@data-sc-note-stamp="external"]')
        internal = read.xpath('.//*[@data-sc-note-stamp="internal"]')
        self.assertEqual(len(ext), 1)
        self.assertEqual(len(internal), 1)
        self.assertIn('o_sc_meta', ext[0].get('class'))
        self.assertEqual(_text(ext[0]), self.injury.last_external_note_info)
        self.assertEqual(_text(internal[0]), self.injury.last_internal_note_info)
        self.assertIn('PC TP', _text(ext[0]))

    def test_coach_sees_the_external_stamp_only(self):
        self._write_notes()
        self._login_coach()
        text, tree = self._get(self._card_url())
        read = self._notes_read(tree)
        self.assertEqual(len(read.xpath('.//*[@data-sc-note-stamp="external"]')), 1)
        self.assertFalse(read.xpath('.//*[@data-sc-note-stamp="internal"]'))
        self.assertNotIn('Synthetic internal 1669', text)

    def test_no_stamp_without_history(self):
        fresh = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic blank 1669'})
        self._login_tp()
        _text_, tree = self._get(self._card_url(fresh))
        self.assertFalse(self._notes_read(tree, fresh).xpath('.//*[@data-sc-note-stamp]'))


@tagged('post_install', '-at_install')
class TestCardNoteStampsI18n1669(Stamps1669Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.tp.write({'lang': 'fr_CA'})

    def test_read_stamp_in_french(self):
        self._write_notes()
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text_, tree = self._get(self._card_url())
        stamp = self._notes_read(tree).xpath('.//*[@data-sc-note-stamp="external"]')[0]
        self.assertTrue(_text(stamp).startswith('Dernière note le '), _text(stamp))
        self.assertIn(' par PC TP', _text(stamp))


@tagged('post_install', '-at_install')
class TestCardNoteStampsTour1669(Stamps1669Common):
    browser_size = '1366x768'

    def test_stamp_refreshes_after_save(self):
        self.start_tour(self._card_url(), 'sc_1669_note_stamp', login='pc.tp@example.com')
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'T1669 tour new note')
