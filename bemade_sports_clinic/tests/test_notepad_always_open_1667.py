"""Task 1667 — the Notepad's quick-note form is always shown: no « + Ajouter »
header toggle, no collapsible wrapper. Synthetic fixtures only.

Acceptance criteria:

* AC-1 /my/notepad renders the quick-note textarea and its « Ajouter »
  submit inside a plain card (no <details>, no <summary>), with no list
  header « + Ajouter » toggle controlling it.
* AC-2 « Lier cette note (facultatif) » stays a collapsible disclosure.
* AC-3 Browser (phone 390 px + laptop 1366 px,
  static/tests/tours/sc_notepad_always_open_1667_tours.js): the textarea
  and « Ajouter » are visible with no tap, nothing is auto-focused (#1646),
  the link disclosure opens, and adding a note works.

The real iPhone rendering stays UNVERIFIED until /dev-review.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

NOTE = 'Tour 1667 synthetic quick note'


class Notepad1667Common(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)


@tagged('post_install', '-at_install')
class TestNotepadAlwaysOpen1667(Notepad1667Common):

    def test_form_is_a_plain_card(self):
        self._login_tp()
        _text, tree = self._get('/my/notepad')
        card = tree.xpath('//*[@id="sc_notepad_add"]')
        self.assertEqual(len(card), 1)
        self.assertEqual(card[0].tag, 'section')
        self.assertIsNone(card[0].get('open'))
        self.assertFalse(tree.xpath('//details[@id="sc_notepad_add"]'))
        self.assertFalse(card[0].xpath('./summary'))
        self.assertEqual(card[0].xpath('.//form/@action'), ['/my/notepad/add'])
        self.assertTrue(card[0].xpath('.//button[@type="submit"][@data-sc-action="note.add"]'))

    def test_no_add_toggle_in_the_header(self):
        self._login_tp()
        _text, tree = self._get('/my/notepad')
        self.assertFalse(tree.xpath('//*[@data-sc-section="notepad.header"]'))
        self.assertFalse(tree.xpath('//*[@data-sc-list-add-toggle][@aria-controls="sc_notepad_add"]'))
        self.assertFalse(tree.xpath('//*[@data-sc-action="notepad.add"]'))

    def test_link_disclosure_is_still_collapsible(self):
        self._login_tp()
        _text, tree = self._get('/my/notepad')
        disclosure = tree.xpath('//form[@id="quick-add"]//details[contains(@class, "o_sc_disclosure")]')
        self.assertEqual(len(disclosure), 1)
        self.assertIsNone(disclosure[0].get('open'))
        self.assertTrue(disclosure[0].xpath('./summary'))


class _NotepadTours1667:

    def test_notepad_always_open(self):
        self.start_tour('/my/notepad', 'sc_1667_notepad_always_open', login='pc.tp@example.com')
        self.assertEqual(self.env['sports.quick.note'].sudo().search_count([
            ('note', '=', NOTE), ('user_id', '=', self.tp.id)]), 1)


@tagged('post_install', '-at_install')
class TestNotepadAlwaysOpenPhone1667(_NotepadTours1667, Notepad1667Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestNotepadAlwaysOpenLaptop1667(_NotepadTours1667, Notepad1667Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
