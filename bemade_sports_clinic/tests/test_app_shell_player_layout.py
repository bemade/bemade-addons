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
  under the play status (task 1615; task 1753: the status just above the
  read view, outside it), the one return date next (task 1630:
  the allergies are the header's pills, test_medical_alerts_1630); a therapist edits
  the recommendation (live, stamp + history) in the header's edit view.
* UC-PL5 Emergency contacts are on the Info tab (cards and « Add Emergency
  Contact »); adding or editing one comes back to the Info tab.
"""
import json
from datetime import date

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


@tagged('post_install', '-at_install')
class TestAppShellPlayerLayout(PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_medical(cls.player, allergies=[('Synthetic peanuts', False)])
        cls.player.sudo().write({'date_of_birth': date(2010, 5, 4),
                                 'training_recommendation': 'Synthetic bike'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _tabs(tree):
        return tree.xpath('//nav[@data-pk-tabs]/a/@data-pk-tab')

    @staticmethod
    def _active(tree):
        return tree.xpath('//nav[@data-pk-tabs]/a[@aria-selected="true"]/@data-pk-tab')

    @staticmethod
    def _owl(node):
        return {json.loads(p)['field']: json.loads(p) for p in node.xpath(
            './/owl-component[@name="bemade_portal_kit.pk_autosave_field"]/@props')
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
        self.assertFalse(tree.xpath('//section[@data-pk-tab-panel="overview"]'))
        self.assertFalse(tree.xpath('//section[@data-pk-tab-panel="contacts"]'))
        _text, tree = self._get(self._url(tab='overview'))
        self.assertEqual(self._active(tree), ['injuries'])
        _text, tree = self._get(self._url(tab='contacts'))
        self.assertEqual(self._active(tree), ['info'])
        info = tree.xpath('//nav[@data-pk-tabs]/a[@data-pk-tab="info"]')[0]
        self.assertIn('contacts', (info.get('data-pk-tab-aliases') or '').split())

    # -- UC-PL2 ----------------------------------------------------------
    def test_header_status_selector(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='injuries'))
        hero = tree.xpath('//*[@data-pk-section="player.hero"]')[0]
        self.assertEqual(hero.get('data-pk-edit-card'), 'player-header')
        # Task 1736 (deliberate update): the pencil sits in the hero's top-bar
        # icon group (with the ★), no longer a direct child of the card.
        self.assertEqual(len(hero.xpath('.//*[@data-sc-card-icons]/button[@data-pk-edit-toggle]')), 1)
        self.assertEqual(len(hero.xpath('.//button[@data-pk-edit-toggle]')), 1)
        read = hero.xpath('./*[@data-pk-edit-view="read"]')[0]
        edit = hero.xpath('./*[@data-pk-edit-view="edit"]')[0]
        self.assertEqual(edit.get('hidden'), 'hidden')
        # Task 1627: the status pills are live dropdowns (no stage chip, no
        # selector behind the pencil). Task 1753 (deliberate update): they
        # sit outside the read view, so the pencil no longer hides them.
        status = hero.xpath('./*[@data-pk-section="player.status"]')[0]
        self.assertFalse(hero.xpath('.//*[@data-sc-stage-chip]'))
        self.assertEqual(len(status.xpath('./*[@data-pk-section="player.status.readonly"]'
                                          '//button[contains(@class, "o_pk_pill_select")]')), 2)
        self.assertFalse(read.xpath('.//*[@data-pk-section="player.status"]'))
        self.assertFalse(read.xpath('.//owl-component'))
        self.assertFalse(status.xpath('.//owl-component'))
        self.assertNotIn('sc_status', self._owl(edit))
        self.assertFalse(tree.xpath('//owl-component[contains(@props, \'"sc_status"\')]'))
        self._login_coach()
        _text, tree = self._get(self._url(tab='injuries'))
        hero = tree.xpath('//*[@data-pk-section="player.hero"]')[0]
        self.assertNotIn('sc_status', self._owl(hero))
        self.assertIsNone(hero.get('data-pk-edit-card'))
        self.assertFalse(hero.xpath('.//*[@data-pk-edit-toggle]'))
        self.assertFalse(hero.xpath('.//*[@data-pk-edit-view="edit"]'))
        self.assertTrue(hero.xpath('.//*[@data-pk-section="player.status.readonly"]'))
        self.assertFalse(hero.xpath('.//*[@data-pk-section="player.status.readonly"]//button'))

    def _assert_training_title(self, section):
        """Task 1629: ``section`` opens with the h3 ``o_pk_edit_card_title``
        « Training Recommendation » and its « History » link right after the
        label (``o_pk_section_more o_pk_link_btn``), the only one inside."""
        title = section.xpath('./*')[0]
        self.assertEqual(title.tag, 'h3')
        self.assertIn('o_pk_edit_card_title', title.get('class').split())
        label, link = title.xpath('./*')
        self.assertEqual(label.text_content().strip(), 'Training Recommendation')
        self.assertTrue({'o_pk_section_more', 'o_pk_link_btn'} <= set(link.get('class').split()))
        self.assertEqual(section.xpath('.//*[@data-pk-sheet-open="sc_training_history_sheet"]'), [link])

    # -- UC-PL3 / UC-PL4 -------------------------------------------------
    def test_info_cards(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='info'))
        panel = tree.xpath('//section[@data-pk-tab-panel="info"]')[0]
        identity = panel.xpath('.//*[@data-pk-edit-card="identity"]')[0]
        read = ' '.join(identity.xpath('.//*[@data-pk-edit-view="read"]')[0].text_content().split())
        self.assertIn('Date of birth', read)
        self.assertIn('Age', read)
        self.assertIn('date_of_birth', self._owl(identity))
        medical = panel.xpath('.//*[@data-pk-edit-card="medical"]')[0]
        self.assertNotIn('Date of birth', medical.text_content())
        self.assertNotIn('date_of_birth', self._owl(medical))
        # Owner review 2026-10-14: the training recommendation left the Info
        # tab for the header; task 1615: right under the play status, then
        # « Retour prévu » (the full order: test_header_order_1615).
        self.assertFalse(panel.xpath('.//*[@data-pk-section="player.training"]'))
        training = tree.xpath('//*[@data-pk-section="player.training"]')
        self.assertEqual(len(training), 1)
        hero = tree.xpath('//*[@data-pk-section="player.hero"]')[0]
        read = hero.xpath('./*[@data-pk-edit-view="read"]')[0]
        self.assertIs(training[0].getparent(), read)
        # Task 1611: the banner sits in its always-rendered read-fragment
        # holder (filled / cleared in place).
        # Task 1753 (deliberate update): the play status sits just above
        # the read view (outside it), so the banner opens the read view.
        self.assertIsNone(training[0].getprevious())
        self.assertEqual(read.getprevious().get('data-pk-section'), 'player.status')
        self.assertEqual(training[0].getnext().get('data-pk-section'), 'player.return')
        # Task 1630: no allergies banner in the read view — the pill in the
        # header's top row, its details in the popup.
        self.assertFalse(read.xpath('./*[@data-pk-section="player.allergies"]'))
        self.assertTrue(hero.xpath('.//*[@data-pk-section="player.medical"]//button[@data-sc-med-pill="allergy"]'))
        self.assertIn('Synthetic peanuts', tree.xpath(
            '//dialog[@id="sc_med_player_allergy_%s"]' % self.player.id)[0].text_content())
        self.assertIn('Synthetic bike', training[0].text_content())
        # Task 1629: an all-caps in-card title with ONE History link after it.
        self._assert_training_title(training[0])
        # Review fixes 2026-10-18: the therapist edits it in the header's
        # edit view (live, with its History). Task 1629: the same title +
        # link heads it; the island draws no second link.
        edit = hero.xpath('./*[@data-pk-edit-view="edit"]')[0]
        training_edit = edit.xpath('./*[@data-pk-section="player.training.edit"]')[0]
        self.assertIn('training_recommendation', self._owl(training_edit))
        self._assert_training_title(training_edit)
        self.assertFalse(training_edit.xpath('.//owl-component[contains(@props, "sc_training_history_sheet")]'))
        self._login_coach()
        _text, tree = self._get(self._url(tab='info'))
        self.assertFalse(tree.xpath(
            '//section[@data-pk-tab-panel="info"]//*[@data-pk-section="player.training"]'))
        training = tree.xpath('//*[@data-pk-section="player.hero"]/*[@data-pk-edit-view="read"]'
                              '/*[@data-pk-section="player.training"]')[0]
        self.assertIn('Synthetic bike', training.text_content())
        self.assertNotIn('training_recommendation', self._owl(training))
        self._assert_training_title(training)

    # -- UC-PL5 ----------------------------------------------------------
    def test_contacts_on_info_tab(self):
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get(self._url(tab='info'))
            panel = tree.xpath('//section[@data-pk-tab-panel="info"]')[0]
            self.assertTrue(panel.xpath('.//*[@data-pk-section="player.contacts"]'))
            form = panel.xpath('.//form[@data-sc-form="contact.add"]')[0]
            back = form.xpath('.//input[@name="return_url"]/@value')[0]
            self.assertTrue(back.endswith('#info') or 'tab=info' in back, back)
        self._login_tp()
        resp = self.url_open('/my/player/contact/add?patient_id=%s' % self.player.id, allow_redirects=False)
        self.assertIn('tab=info', resp.headers.get('Location', ''))
