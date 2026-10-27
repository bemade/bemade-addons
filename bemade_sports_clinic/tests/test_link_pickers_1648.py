"""Task 1648 — the type-to-filter picker on the app's link fields, and the
Notepad note's « Archiver ». Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 The Notepad's new-note links (team, player, injury, event) and the
  note card's link fields are picker selects (data-sc-picker + a key), the
  options carrying the narrowing data (player / event -> teams, injury ->
  player); the player is a plain select now (no legacy combo).
* UC-2 No-JS fallback: the select posts the value as before (the note is
  linked to the posted player).
* UC-3 The add-note « Link to Injury » and the upload « injury » selects are
  pickers too.
* UC-4 The note card's archive button reads « Archive » (fr_CA « Archiver »).
* UC-5 (tours) Notepad: a team narrows the players, a player the injuries,
  clearing the team widens; type part of a name, pick, add: the note is
  linked. The add-note injury picker on the player page.
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class Pickers1648Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['sports.team.staff'].create({
            'team_id': cls.team_b.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist'})
        cls.zoe = env['sports.patient'].create({'first_name': 'Zoé', 'last_name': 'Pickerline'})
        cls.zoe.team_ids = [Command.set([cls.team_b.id])]
        cls.zoe_injury = env['sports.patient.injury'].create({
            'patient_id': cls.zoe.id, 'diagnosis': 'Synthetic wrist'})
        cls.zoe_injury.with_context(mail_notrack=True).write({'stage': 'active'})

    def setUp(self):
        super().setUp()
        self._switch(True)


@tagged('post_install', '-at_install')
class TestLinkPickers1648(Pickers1648Common):

    def _notepad(self):
        resp = self.url_open('/my/notepad')
        self.assertEqual(resp.status_code, 200)
        return lxml_html.fromstring(resp.text)

    def test_notepad_links_are_pickers(self):
        self._login_tp()
        tree = self._notepad()
        form = tree.xpath('//form[@id="quick-add"]')[0]
        keys = {s.get('name'): s.get('data-sc-picker-key')
                for s in form.xpath('.//select[@data-sc-picker="1"]')}
        self.assertEqual(keys, {'team_id': 'team', 'patient_id': 'player',
                                'injury_id': 'injury', 'event_id': 'event'})
        zoe = form.xpath('.//select[@name="patient_id"]/option[@value="%s"]' % self.zoe.id)[0]
        self.assertEqual(zoe.get('data-sc-teams'), str(self.team_b.id))
        inj = form.xpath('.//select[@name="injury_id"]/option[@value="%s"]' % self.zoe_injury.id)[0]
        self.assertEqual(inj.get('data-sc-player'), str(self.zoe.id))
        self.assertFalse(form.xpath('.//*[contains(@class, "o_patient_combo")]'))

    def test_card_links_and_archive_label(self):
        self._login_tp()
        self.url_open('/my/notepad/add', data={'csrf_token': self._csrf(), 'note': 'Synthetic card note'})
        tree = self._notepad()
        card = tree.xpath('//article[contains(@class, "o_sc_quick_note")]')[0]
        props = ' '.join(card.xpath('.//owl-component/@props'))
        for key in ('"pickerKey": "team"', '"pickerKey": "player"', '"pickerKey": "injury"', '"pickerKey": "event"'):
            self.assertIn(key, props)
        self.assertIn('"optionMeta"', props)
        archive = card.xpath('.//button[@data-sc-action="note.archive"]')[0]
        self.assertEqual(archive.text_content().strip(), 'Archive')

    def test_no_js_post_links_the_player(self):
        self._login_tp()
        self.url_open('/my/notepad/add', data={
            'csrf_token': self._csrf(), 'note': 'Synthetic posted note', 'patient_id': str(self.zoe.id)})
        note = self.env['sports.quick.note'].search([('note', '=', 'Synthetic posted note')])
        self.assertEqual(note.patient_id, self.zoe)

    def test_player_page_injury_pickers(self):
        self._login_tp()
        resp = self.url_open('/my/player?player_id=%s&tab=notes' % self.player.id)
        tree = lxml_html.fromstring(resp.text)
        self.assertEqual(tree.xpath('//select[@id="sc_note_injury"]/@data-sc-picker'), ['1'])
        self.assertTrue(tree.xpath('//form[@data-sc-doc-upload]//select[@name="injury_id"][@data-sc-picker="1"]'))


@tagged('post_install', '-at_install')
class TestLinkPickersTours1648(Pickers1648Common):
    browser_size = '1366x768'

    def test_notepad_tour(self):
        self.start_tour('/my/notepad', 'sc_1648_notepad', login='pc.tp@example.com')
        note = self.env['sports.quick.note'].search([('note', '=', 'Tour 1648 synthetic note')])
        self.assertEqual(note.patient_id, self.zoe)
        self.assertEqual(note.injury_id, self.zoe_injury)

    def test_card_picker_autosaves(self):
        note = self.env['sports.quick.note'].create({'note': 'Synthetic card 1648', 'user_id': self.tp.id})
        self.start_tour('/my/notepad', 'sc_1648_card', login='pc.tp@example.com')
        note.invalidate_recordset()
        self.assertEqual(note.patient_id, self.zoe)

    def test_add_note_injury_picker(self):
        self.start_tour('/my/player?player_id=%s&tab=notes' % self.player.id, 'sc_1648_note_injury',
                        login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestLinkPickersPhone1648(Pickers1648Common):
    browser_size = '390x844'

    def test_notepad_tour_phone(self):
        self.start_tour('/my/notepad', 'sc_1648_notepad', login='pc.tp@example.com')
