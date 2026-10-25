"""Task 1675 — the injury card's external and internal notes are edited
independently (one pencil each). Synthetic fixtures only.

Acceptance criteria:

* AC-1 The Notes section (``injury.notes``) holds two edit cards:
  ``injury-notes-external`` and, for a therapist, ``injury-notes-internal``;
  each has ONE pencil, its own read view (its own read fragment
  ``notes-external`` / ``notes-internal``, the note + its #1669 stamp) and
  an edit view with only its own autosave field.
* AC-2 ONE « History » link in the Notes section head (not in the note
  cards), its sheet keeps the scope filters.
* AC-3 Coach: the external card only (read + stamp; owner review
  2026-10-25: no pencil — coaches read the external note, they no longer
  edit it), no internal card, no internal text.
* AC-4 Browser (phone 390 px + laptop 1366 px, tour
  ``sc_1675_split_notes``): the external pencil opens only the external
  editor; a save refreshes its stamp and leaves the internal block as it
  was; then the internal pencil does the same for the internal note.
"""
import json

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class Split1675Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury.sudo().with_context(mail_notrack=True).write({
            'external_notes': 'Synthetic ext 1675', 'internal_notes': 'Synthetic int 1675'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _url(self):
        return '/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, self.injury.id)

    def _section(self, tree):
        nodes = tree.xpath('//details[@id="injury-%s"]//section[@data-sc-section="injury.notes"]' % self.injury.id)
        self.assertEqual(len(nodes), 1)
        return nodes[0]

    @staticmethod
    def _fields(node):
        return [json.loads(p)['field'] for p in node.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')]


@tagged('post_install', '-at_install')
class TestSplitInjuryNotes1675(Split1675Common):

    def test_therapist_two_cards(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        section = self._section(tree)
        self.assertIsNone(section.get('data-sc-edit-card'))
        key = 'sports.patient.injury:%s:' % self.injury.id
        for scope in ('external', 'internal'):
            cards = section.xpath('.//*[@data-sc-edit-card="injury-notes-%s"]' % scope)
            self.assertEqual(len(cards), 1, scope)
            card = cards[0]
            self.assertEqual(len(card.xpath('.//button[@data-sc-edit-toggle]')), 1, scope)
            read = card.xpath('./*[@data-sc-edit-view="read"]')[0]
            self.assertEqual(read.get('data-sc-fragment'), key + 'notes-%s' % scope)
            self.assertIn('Synthetic %s 1675' % scope[:3], read.text_content())
            edit = card.xpath('./*[@data-sc-edit-view="edit"]')[0]
            self.assertEqual(edit.get('hidden'), 'hidden')
            self.assertEqual(self._fields(edit), ['%s_notes' % scope])

    def test_one_history_in_the_section_head(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        section = self._section(tree)
        links = section.xpath('.//*[starts-with(@data-sc-sheet-open, "sc_note_history_sheet_")]')
        self.assertEqual(len(links), 1)
        self.assertTrue(links[0].xpath('parent::*/parent::div[contains(@class, "o_sc_edit_card_head")]'
                                       '/parent::section[@data-sc-section="injury.notes"]'))
        self.assertFalse(links[0].xpath('ancestor::*[@data-sc-edit-card][ancestor::section[@data-sc-section="injury.notes"]]'))

    def test_coach_external_only(self):
        self._login_coach()
        text, tree = self._get(self._url())
        section = self._section(tree)
        self.assertEqual(len(section.xpath('.//*[@data-sc-edit-card="injury-notes-external"]')), 1)
        self.assertFalse(section.xpath('.//*[@data-sc-edit-card="injury-notes-internal"]'))
        # Owner review 2026-10-25: the coach reads it — no pencil, no editor.
        external = section.xpath('.//*[@data-sc-edit-card="injury-notes-external"]')[0]
        self.assertFalse(external.xpath('.//button[@data-sc-edit-toggle]'))
        self.assertEqual(self._fields(section), [])
        self.assertIn('Synthetic ext 1675', external.text_content())
        self.assertNotIn('Synthetic int 1675', text)


class _SplitTours1675:

    def test_split_notes_tour(self):
        self.start_tour(self._url(), 'sc_1675_split_notes', login='pc.tp@example.com')
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'T1675 new external')
        self.assertEqual(self.injury.internal_notes, 'T1675 new internal')


@tagged('post_install', '-at_install')
class TestSplitInjuryNotesPhone1675(_SplitTours1675, Split1675Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestSplitInjuryNotesLaptop1675(_SplitTours1675, Split1675Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
