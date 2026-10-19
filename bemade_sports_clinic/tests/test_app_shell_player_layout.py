"""Player page layout (owner review 2026-10-11). Synthetic fixtures only.

Acceptance criteria:

* UC-PL1 No « Overview » and no « Contacts » tab: the player page opens on
  « Injuries ». Old links still land: ``?tab=overview`` opens Injuries,
  ``?tab=contacts`` (and the ``#contacts`` fragment) opens Info.
* UC-PL2 The page header carries the play status. Review fixes 2026-10-18:
  the header is a READ view with one pencil — everyone reads the status
  label + Match / Practice chips there; a therapist's pencil opens the edit
  view holding the play-status selector (the only one on the page); a coach
  has no pencil and no selector.
* UC-PL3 Date of birth and age sit in the « Player » card (read view, and
  the date in its edit view), no longer in « Medical Information ».
* UC-PL4 The training recommendation (with its history link) sits in the
  page header (owner review 2026-10-14 — no longer on the Info tab), right
  under the play status (task 1615), the one return date next and the
  allergies callout after (header read view, everyone); a therapist edits
  the recommendation (live, stamp + history) in the header's edit view.
* UC-PL5 Emergency contacts are on the Info tab (cards and « Add Emergency
  Contact »); adding or editing one comes back to the Info tab.
"""
import json
from datetime import date

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


@tagged('post_install', '-at_install')
class TestAppShellPlayerLayout(PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.sudo().write({'date_of_birth': date(2010, 5, 4), 'allergies': 'Synthetic peanuts',
                                 'training_recommendation': 'Synthetic bike'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _tabs(tree):
        return tree.xpath('//nav[@data-sc-tabs]/a/@data-sc-tab')

    @staticmethod
    def _active(tree):
        return tree.xpath('//nav[@data-sc-tabs]/a[@aria-selected="true"]/@data-sc-tab')

    @staticmethod
    def _owl(node):
        return {json.loads(p)['field']: json.loads(p) for p in node.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')
            if json.loads(p).get('field')}

    # -- UC-PL1 ----------------------------------------------------------
    def test_tabs_and_default(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s' % self.player.id)
        tabs = self._tabs(tree)
        self.assertNotIn('overview', tabs)
        self.assertNotIn('contacts', tabs)
        self.assertEqual(tabs[:2], ['injuries', 'info'])
        self.assertEqual(self._active(tree), ['injuries'])
        self.assertFalse(tree.xpath('//section[@data-sc-tab-panel="overview"]'))
        self.assertFalse(tree.xpath('//section[@data-sc-tab-panel="contacts"]'))
        _text, tree = self._get(self._url(tab='overview'))
        self.assertEqual(self._active(tree), ['injuries'])
        _text, tree = self._get(self._url(tab='contacts'))
        self.assertEqual(self._active(tree), ['info'])
        info = tree.xpath('//nav[@data-sc-tabs]/a[@data-sc-tab="info"]')[0]
        self.assertIn('contacts', (info.get('data-sc-tab-aliases') or '').split())

    # -- UC-PL2 ----------------------------------------------------------
    def test_header_status_selector(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='injuries'))
        hero = tree.xpath('//*[@data-sc-section="player.hero"]')[0]
        self.assertEqual(hero.get('data-sc-edit-card'), 'player-header')
        self.assertEqual(len(hero.xpath('./button[@data-sc-edit-toggle]')), 1)
        read = hero.xpath('./*[@data-sc-edit-view="read"]')[0]
        edit = hero.xpath('./*[@data-sc-edit-view="edit"]')[0]
        self.assertEqual(edit.get('hidden'), 'hidden')
        self.assertTrue(read.xpath('.//*[@data-sc-section="player.status.readonly"]//*[@data-sc-stage-chip]'))
        self.assertFalse(read.xpath('.//owl-component'))
        self.assertEqual(self._owl(edit)['sc_status']['inputType'], 'segmented')
        self.assertEqual(len(tree.xpath('//owl-component[contains(@props, \'"sc_status"\')]')), 1)
        self._login_coach()
        _text, tree = self._get(self._url(tab='injuries'))
        hero = tree.xpath('//*[@data-sc-section="player.hero"]')[0]
        self.assertNotIn('sc_status', self._owl(hero))
        self.assertIsNone(hero.get('data-sc-edit-card'))
        self.assertFalse(hero.xpath('.//*[@data-sc-edit-toggle]'))
        self.assertFalse(hero.xpath('.//*[@data-sc-edit-view="edit"]'))
        self.assertTrue(hero.xpath('.//*[@data-sc-section="player.status.readonly"]'))

    # -- UC-PL3 / UC-PL4 -------------------------------------------------
    def test_info_cards(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='info'))
        panel = tree.xpath('//section[@data-sc-tab-panel="info"]')[0]
        identity = panel.xpath('.//*[@data-sc-edit-card="identity"]')[0]
        read = ' '.join(identity.xpath('.//*[@data-sc-edit-view="read"]')[0].text_content().split())
        self.assertIn('Date of birth', read)
        self.assertIn('Age', read)
        self.assertIn('date_of_birth', self._owl(identity))
        medical = panel.xpath('.//*[@data-sc-edit-card="medical"]')[0]
        self.assertNotIn('Date of birth', medical.text_content())
        self.assertNotIn('date_of_birth', self._owl(medical))
        # Owner review 2026-10-14: the training recommendation left the Info
        # tab for the header; task 1615: right under the play status, then
        # « Retour prévu » (the full order: test_header_order_1615).
        self.assertFalse(panel.xpath('.//*[@data-sc-section="player.training"]'))
        training = tree.xpath('//*[@data-sc-section="player.training"]')
        self.assertEqual(len(training), 1)
        hero = tree.xpath('//*[@data-sc-section="player.hero"]')[0]
        read = hero.xpath('./*[@data-sc-edit-view="read"]')[0]
        self.assertIs(training[0].getparent(), read)
        # Task 1611: the banner sits in its always-rendered read-fragment
        # holder (filled / cleared in place).
        self.assertEqual(training[0].getprevious().get('data-sc-section'), 'player.status')
        self.assertEqual(training[0].getnext().get('data-sc-section'), 'player.return')
        allergies = read.xpath('./*[@data-sc-section="player.allergies"]')[0]
        self.assertTrue(allergies.xpath('./*[contains(@class, "o_sc_banner")]'))
        self.assertIn('Synthetic peanuts', allergies.text_content())
        self.assertIn('Synthetic bike', training[0].text_content())
        self.assertTrue(training[0].xpath('.//*[@data-sc-sheet-open="sc_training_history_sheet"]'))
        # Review fixes 2026-10-18: the therapist edits it in the header's
        # edit view (live, with its History).
        edit = hero.xpath('./*[@data-sc-edit-view="edit"]')[0]
        training_edit = edit.xpath('./*[@data-sc-section="player.training.edit"]')[0]
        self.assertIn('training_recommendation', self._owl(training_edit))
        self.assertTrue(training_edit.xpath('.//owl-component[contains(@props, "sc_training_history_sheet")]'))
        self._login_coach()
        _text, tree = self._get(self._url(tab='info'))
        self.assertFalse(tree.xpath(
            '//section[@data-sc-tab-panel="info"]//*[@data-sc-section="player.training"]'))
        training = tree.xpath('//*[@data-sc-section="player.hero"]/*[@data-sc-edit-view="read"]'
                              '/*[@data-sc-section="player.training"]')[0]
        self.assertIn('Synthetic bike', training.text_content())
        self.assertNotIn('training_recommendation', self._owl(training))
        self.assertTrue(training.xpath('.//*[@data-sc-sheet-open="sc_training_history_sheet"]'))

    # -- UC-PL5 ----------------------------------------------------------
    def test_contacts_on_info_tab(self):
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get(self._url(tab='info'))
            panel = tree.xpath('//section[@data-sc-tab-panel="info"]')[0]
            self.assertTrue(panel.xpath('.//*[@data-sc-section="player.contacts"]'))
            form = panel.xpath('.//form[@data-sc-form="contact.add"]')[0]
            back = form.xpath('.//input[@name="return_url"]/@value')[0]
            self.assertTrue(back.endswith('#info') or 'tab=info' in back, back)
        self._login_tp()
        resp = self.url_open('/my/player/contact/add?patient_id=%s' % self.player.id, allow_redirects=False)
        self.assertIn('tab=info', resp.headers.get('Location', ''))
