"""Task 1629 — the player page's training recommendation title. Synthetic
fixtures only.

Acceptance criteria (the English structure: test_app_shell_player_status
``_history_link`` and test_app_shell_player_layout; the browser half: the
``sc_training_history_refresh`` tour):

* AC-1 Read view (therapists and coaches): « Training Recommendation » is an
  all-caps in-card title (``h3.o_sc_edit_card_title``, as « Details » /
  « Notes ») heading the ``player.training`` section, with « History »
  (``o_sc_section_more o_sc_link_btn``) right after the label, inside the
  title; it opens ``sc_training_history_sheet``. The value and its stamp
  follow, with no label row of their own.
* AC-2 Pencil edit view (therapists): the same title + link heads
  ``player.training.edit``; the autosave island draws no second link (no
  ``historySheet`` prop) and keeps its label, visually hidden
  (``labelHidden``), as the textarea's accessible name.
* AC-3 Exactly one History link per mode.
* AC-4 French: « Recommandation d'entraînement » + « Historique » in both
  modes, the island's label too (render, website-aware).
* AC-5 The clinic dossier is unchanged (its view is not touched).
"""
import json

from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestTrainingTitleI18n1629(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _sections(self, login):
        login()
        text = self._fr('/my/player?player_id=%s' % self.player.id)
        tree = lxml_html.fromstring(text)
        return tree, tree.xpath('//*[@data-sc-section="player.training"]'), \
            tree.xpath('//*[@data-sc-section="player.training.edit"]')

    def _assert_title(self, section):
        title = section.xpath('./*')[0]
        self.assertEqual(title.tag, 'h3')
        self.assertIn('o_sc_edit_card_title', title.get('class').split())
        label, link = title.xpath('./*')
        self.assertEqual(label.text_content().strip(), "Recommandation d'entraînement")
        self.assertEqual(link.text_content().strip(), 'Historique')
        self.assertEqual(link.get('data-sc-sheet-open'), 'sc_training_history_sheet')
        self.assertEqual(section.xpath('.//*[@data-sc-sheet-open="sc_training_history_sheet"]'), [link])

    def test_therapist_read_and_edit_in_french(self):
        _tree, read, edit = self._sections(self._login_tp)
        self.assertEqual((len(read), len(edit)), (1, 1))
        self._assert_title(read[0])
        self._assert_title(edit[0])
        props = [json.loads(c.get('props')) for c in edit[0].xpath('.//owl-component')]
        props = [p for p in props if p.get('field') == 'training_recommendation']
        self.assertEqual(len(props), 1)
        self.assertEqual(props[0]['label'], "Recommandation d'entraînement")
        self.assertIs(props[0]['labelHidden'], True)
        self.assertNotIn('historySheet', props[0])

    def test_coach_read_in_french(self):
        _tree, read, edit = self._sections(self._login_coach)
        self.assertEqual((len(read), len(edit)), (1, 0))
        self._assert_title(read[0])
