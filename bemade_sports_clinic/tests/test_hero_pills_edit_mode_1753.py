"""Task 1753 — the player header keeps its status and medical pills visible
while the card is edited. Synthetic fixtures only.

Acceptance criteria:

* AC-1 Therapist: the play status block (``player.status``: the Match /
  Practice pills and the « Allergies » / « Medical alert » pills) is a
  direct child of the header card, right after its top row and right
  before the read view — outside BOTH ``data-sc-edit-view`` blocks, so the
  header pencil (which hides the read view) no longer hides it.
* AC-2 Coach: the same place (no pencil, no edit view), read-only pills.
* AC-3 Nothing duplicated or lost: the page carries ONE ``status`` and ONE
  ``medical-pills`` fragment for the player, with their #1611 keys and
  section names unchanged, and the ``status`` fragment still matches the
  page (in-place refresh after a save).
* AC-4 (browser, tour ``sc_1753_hero_pills_edit``): as a therapist, open
  the header pencil — the status and medical pills stay visible; change
  Match from the edit mode: the pill recolours in place, the card stays in
  its edit mode, no reload and no duplicated pills; « Done » (✓) brings
  back the read view with the pills shown once.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon
from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_status_pills_1627 import StatusPillsMixin


@tagged('post_install', '-at_install')
class TestHeroPillsEditMode1753(StatusPillsMixin, FragmentsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_medical(cls.player, allergies=[('Synthetic dust', True)])
        cls.player.sudo().write({'match_status': 'yes', 'practice_status': 'yes',
                                 'training_recommendation': 'Synthetic cycling',
                                 'predicted_return_date': '2030-02-01', 'return_date': '2029-12-01'})

    def _url(self, tab='injuries'):
        return '/my/player?player_id=%s&tab=%s&team_id=%s' % (self.player.id, tab, self.team_a.id)

    @staticmethod
    def _hero(tree):
        return tree.xpath('//*[@data-pk-section="player.hero"]')[0]

    def _status_block(self, tree):
        """The header's ``player.status`` block, checked to sit outside every
        read / edit view, between the top row and the read view."""
        hero = self._hero(tree)
        blocks = hero.xpath('.//*[@data-pk-section="player.status"]')
        self.assertEqual(len(blocks), 1)
        status = blocks[0]
        self.assertIs(status.getparent(), hero)
        self.assertFalse(status.xpath('ancestor::*[@data-sc-edit-view]'))
        self.assertFalse(status.xpath('.//*[@data-sc-edit-view]'))
        self.assertIn('o_sc_hero_top', status.getprevious().get('class'))
        self.assertEqual(status.getnext().get('data-sc-edit-view'), 'read')
        self.assertFalse(hero.xpath('./*[@data-sc-edit-view]//*[@data-pk-section="player.status"]'
                                    ' | ./*[@data-sc-edit-view]//*[@data-pk-section="player.medical"]'))
        return status

    # -- AC-1 --------------------------------------------------------------
    def test_therapist_pills_outside_the_edit_views(self):
        self._login_tp()
        tree = self._page(self._url())
        hero = self._hero(tree)
        self.assertEqual(hero.get('data-pk-edit-card'), 'player-header')
        self.assertEqual(len(hero.xpath('./*[@data-sc-edit-view="edit"]')), 1)
        status = self._status_block(tree)
        self.assertEqual(len(status.xpath('./*[@data-pk-section="player.status.readonly"]'
                                          '//button[contains(@class, "o_pk_pill_select")]')), 2)
        self.assertTrue(status.xpath('./*[@data-pk-section="player.medical"]'
                                     '//button[@data-sc-med-pill="allergy"]'))

    # -- AC-2 --------------------------------------------------------------
    def test_coach_pills_same_place(self):
        self._login_coach()
        tree = self._page(self._url())
        hero = self._hero(tree)
        self.assertFalse(hero.xpath('.//*[@data-sc-edit-view="edit"] | .//*[@data-sc-edit-toggle]'))
        status = self._status_block(tree)
        self.assertEqual(len(status.xpath('.//*[@data-pk-pill-readonly]')), 2)
        self.assertFalse(status.xpath('.//*[@data-pk-section="player.status.readonly"]//button'))

    # -- AC-3 --------------------------------------------------------------
    def test_fragments_once_and_unchanged(self):
        self._login_tp()
        tree = self._page(self._url())
        status = self._status_block(tree)
        for part in ('status', 'medical-pills'):
            nodes = tree.xpath('//*[@data-pk-fragment="%s"]' % self._key(part))
            self.assertEqual(len(nodes), 1, part)
            self.assertIn(nodes[0], status.iter(), part)
        self.assertEqual(self._status_node(tree).get('data-pk-section'), 'player.status.readonly')
        self.assertFragmentMatchesPage(self._url(), self._key('status'))

    # -- AC-4 --------------------------------------------------------------
    def test_tour(self):
        self._set('yes:yes')
        self.start_tour(self._url(), 'sc_1753_hero_pills_edit', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('no', 'yes'))
