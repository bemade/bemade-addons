"""Task 1615: the training recommendation right under the play status.
Review fixes 2026-10-18: the player header is a READ view with ONE pencil
(therapists) and an edit view. Synthetic fixtures only.

Acceptance criteria:

* AC-1 Read view (everyone): the play status (label + Match / Practice
  chips, read-only), then (its very next block) the training recommendation,
  then ONE return date — « Retour prévu » while the player is not Play OK,
  else « Retour réel », a muted « not set » line while that date is empty
  (review fixes 2026-10-18, 1018c) — then the
  allergies holder (banner for therapists, hidden when empty).
* AC-2 Edit view (therapists, behind the header's one pencil): the
  play-status selector, the training recommendation (live), « Retour
  prévu », « Retour réel », the allergies, « Remove player » (edit view
  only), then « Done ». Coaches: no pencil, no edit view.
* AC-3 Nothing else moves: the header still opens on the name / team head
  and ends on the actions row; the #1611 fragment keys of the header
  regions are unchanged (``status`` and ``predicted-return`` are now read
  fragments for everyone).
* AC-4 Clinic dossier: the play status, then the training recommendation,
  in the same « status » card.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon

ORDER = ['player.status', 'player.training', 'player.return', 'player.allergies']
EDIT_ORDER = ['player.status.edit', 'player.training.edit', 'player.predicted_return',
              'player.return_date.edit', 'player.allergies.edit']


@tagged('post_install', '-at_install')
class TestHeaderOrder1615(PlayerInlineCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.sudo().write({'allergies': 'Synthetic pollen', 'training_recommendation': 'Synthetic rowing',
                                 'predicted_return_date': '2030-02-01', 'return_date': '2029-12-01',
                                 'match_status': 'no', 'practice_status': 'no'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    @staticmethod
    def _hero(tree):
        return tree.xpath('//*[@data-sc-section="player.hero"]')[0]

    @staticmethod
    def _children(node):
        return [child for child in node if isinstance(child.tag, str)]

    def _assert_order(self, tree):
        hero = self._hero(tree)
        children = self._children(hero)
        # AC-3: head first, actions last.
        self.assertIn('o_sc_hero_head', children[0].get('class'))
        self.assertIn('o_sc_actions_row', children[-1].get('class'))
        read = hero.xpath('./*[@data-sc-edit-view="read"]')[0]
        blocks = self._children(read)
        sections = [child.get('data-sc-section') for child in blocks]
        self.assertEqual(sections, ORDER, sections)
        self.assertFalse(read.xpath('.//owl-component'))
        return hero, {s: b for s, b in zip(sections, blocks)}

    def test_therapist_order(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='injuries'))
        hero, read = self._assert_order(tree)
        self.assertEqual(hero.get('data-sc-edit-card'), 'player-header')
        self.assertEqual(len(hero.xpath('.//button[@data-sc-edit-toggle]')), 1)
        self.assertTrue(read['player.status'].xpath('.//*[@data-sc-stage-chip]'))
        self.assertIn('Synthetic rowing', read['player.training'].text_content())
        self.assertIn('Synthetic pollen', read['player.allergies'].text_content())
        edit = hero.xpath('./*[@data-sc-edit-view="edit"]')[0]
        self.assertEqual(edit.get('hidden'), 'hidden')
        sections = [c.get('data-sc-section') for c in self._children(edit) if c.get('data-sc-section')]
        self.assertEqual([s for s in sections if s in EDIT_ORDER], EDIT_ORDER, sections)
        fields = {s: c for s, c in zip(sections, [c for c in self._children(edit) if c.get('data-sc-section')])}
        for section, field in (('player.status.edit', 'sc_status'),
                               ('player.training.edit', 'training_recommendation'),
                               ('player.predicted_return', 'predicted_return_date'),
                               ('player.return_date.edit', 'return_date'),
                               ('player.allergies.edit', 'allergies')):
            self.assertTrue(fields[section].xpath('.//owl-component[contains(@props, \'"%s"\')]' % field),
                            section)
        # « Remove player » only in the edit view; « Done » closes it.
        self.assertFalse(read['player.status'].getparent().xpath('.//*[@data-sc-action="player.remove"]'))
        self.assertTrue(edit.xpath('.//button[@data-sc-edit-done]'))

    def test_coach_order(self):
        self._login_coach()
        _text, tree = self._get(self._url(tab='injuries'))
        hero, read = self._assert_order(tree)
        self.assertIsNone(hero.get('data-sc-edit-card'))
        self.assertFalse(hero.xpath('.//*[@data-sc-edit-toggle] | .//*[@data-sc-edit-view="edit"]'))
        self.assertFalse(hero.xpath('.//owl-component'))
        self.assertTrue(read['player.status'].xpath('.//*[@data-sc-section="player.status.readonly"]'))
        self.assertIn('Synthetic rowing', read['player.training'].text_content())
        self.assertIn('2030', read['player.return'].text_content())

    def test_one_return_date(self):
        """Injured (not Play OK): « Retour prévu »; Play OK: « Retour réel »;
        « not set » when the date to show is empty (1018c)."""
        self._login_coach()
        cases = (
            ({'match_status': 'no', 'practice_status': 'no'}, 'predicted', 'Predicted return', '2030'),
            ({'match_status': 'no', 'practice_status': 'yes'}, 'predicted', 'Predicted return', '2030'),
            ({'match_status': 'yes', 'practice_status': 'yes'}, 'actual', 'Actual return', '2029'),
        )
        for vals, kind, label, year in cases:
            self.player.sudo().write(vals)
            _text, tree = self._get(self._url(tab='injuries'))
            _hero, read = self._assert_order(tree)
            ret = read['player.return']
            self.assertEqual(ret.get('data-sc-return-kind'), kind, vals)
            self.assertIn(label, ret.text_content(), vals)
            self.assertIn(year, ret.text_content(), vals)
        # Empty: a muted « not set » line (review fixes 2026-10-18, 1018c).
        self.player.sudo().write({'match_status': 'no', 'practice_status': 'no', 'predicted_return_date': False})
        _text, tree = self._get(self._url(tab='injuries'))
        _hero, read = self._assert_order(tree)
        self.assertEqual(read['player.return'].text_content().strip(), 'Predicted return: not set')
        self.player.sudo().write({'match_status': 'yes', 'practice_status': 'yes', 'return_date': False})
        _text, tree = self._get(self._url(tab='injuries'))
        _hero, read = self._assert_order(tree)
        self.assertEqual(read['player.return'].text_content().strip(), 'Actual return: not set')

    def test_fragment_keys_unchanged(self):
        pid = self.player.id
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get(self._url(tab='injuries'))
            hero = self._hero(tree)
            keys = set(hero.xpath('.//@data-sc-fragment'))
            for part in ('hero-head', 'hero-chips', 'allergies', 'hero-actions', 'status', 'predicted-return',
                         'training'):
                self.assertIn('sports.patient:%s:%s' % (pid, part), keys)
            # Never an island inside a read fragment.
            for node in hero.xpath('.//*[@data-sc-fragment]'):
                self.assertFalse(node.xpath('.//owl-component'), node.get('data-sc-fragment'))


@tagged('post_install', '-at_install')
class TestDossierOrder1615(Clinic1540Common):

    def test_clinic_dossier_order(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player.id))
        card = tree.xpath('//*[@data-sc-section="clinic.dossier.status"]')[0]
        fields = card.xpath('.//owl-component/@props')
        self.assertEqual(len(fields), 2, fields)
        self.assertIn('"sc_status"', fields[0])
        self.assertIn('"training_recommendation"', fields[1])
