"""Task 1634 — player cards: the Match / Practice pills become quick-change
dropdowns (#1627's component, compact) on the team dashboard (« Recent
changes », « Other players to watch »), the team roster and /my/players.
Synthetic fixtures only.

Acceptance criteria:

* AC-1 Therapist: every player card's Match and Practice pills are two
  compact ``button.o_sc_pill_select`` (short label « Match » / « Practice »,
  coloured by value, chevron), each opening a ``role="menu"`` — on the
  dashboard, the roster and /my/players. The full « Match: Yes » text stays
  the button's title.
* AC-2 Coach: the same coloured pills, read-only (no button, no menu) on
  every card.
* AC-3 Menu ids are unique on the page: one player listed in several
  sections (dashboard + roster) gets one menu per section, its id scoped by
  the row scope; every ``aria-controls`` resolves to exactly one node.
* AC-4 Invalid choices are greyed with a hint and post nothing, as in #1627.
* AC-5 In-place refresh: each card's link-row part (dot, pills, ⚡, training
  and « Retour prévu » lines) is the read fragment
  ``sports.patient:<id>:row-<scope>`` — unique on the page, never holding
  the lazy ``.o_sc_row_detail``, kept (not emptied) when a fresh render
  lists the player elsewhere; a ``sc_status`` save refreshes it and the
  fresh fragment carries the new colours, dot and return line plus the
  ``write_date`` / ``old_value`` the next pick posts.
* AC-6 The locked /my/players row (a player the viewer cannot open) stays
  static: no pill button.
* AC-7 Cost: the selection labels are computed once per request (not per
  row); the per-row query bound stays the one of #1593
  (test_app_shell_roster_rows_1593.test_query_count_bounded runs as a
  therapist, so it now covers the dropdown pills).
* AC-8 (tour ``sc_1634_card_pills``): a therapist changes Match on a roster
  card: the card recolours in place (pill + dot), the page does not
  navigate, the same player's dashboard card updates too, ONE fragment
  fetch per pick, and the roster order is unchanged until the next visit.
  ``sc_1634_card_pills_coach``: no button on a coach's cards.
"""
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon

TONES = {'yes': 'green', 'no_contact': 'yellow', 'no': 'red'}
SECTIONS = {
    'dash': 'team.recent_changes',
    'roster': 'team.roster',
    'players': 'players.list',
}


class CardPills1634Common(FragmentsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        now = fields.Datetime.now()
        cls.player.sudo().write({
            'match_status': 'yes', 'practice_status': 'yes',
            'dashboard_last_activity_tp': now, 'dashboard_last_activity_coach': now,
            'training_recommendation': 'Synthetic bike only',
        })
        cls.other = env['sports.patient'].create({
            'first_name': 'Hal', 'last_name': 'Healthy',
            'team_ids': [Command.set([cls.team_a.id])],
        })
        cls.team_url = '/my/team?team_id=%s' % cls.team_a.id

    def _presence(self):
        """The player is on the dashboard's « Recent changes »."""
        return patch.object(
            type(self.env['sports.patient']), '_dashboard_card_presence',
            return_value={'players': {self.player.id}, 'injuries': set()})

    def _set(self, pair):
        match, practice = pair.split(':')
        self.player.sudo().write({'match_status': match, 'practice_status': practice})
        self.player.invalidate_recordset()

    def _key(self, scope, player=None):
        return 'sports.patient:%s:row-%s' % ((player or self.player).id, scope)

    def _row(self, tree, scope, player=None):
        rows = tree.xpath('//*[@data-sc-section="%s"]//*[contains(@class, "o_sc_player_row")]'
                          '[@data-sc-player-id="%s"]' % (SECTIONS[scope], (player or self.player).id))
        self.assertEqual(len(rows), 1, scope)
        return rows[0]

    @staticmethod
    def _toggles(node):
        return {b.getparent().get('data-sc-pill-key'): b
                for b in node.xpath('.//button[contains(@class, "o_sc_pill_select")]')}

    @staticmethod
    def _menu(tree, toggle):
        popups = tree.xpath('//*[@id="%s"]' % toggle.get('aria-controls'))
        return popups


@tagged('post_install', '-at_install')
class TestCardStatusPills1634(CardPills1634Common):

    # -- AC-1 ------------------------------------------------------------
    def test_therapist_cards_have_compact_dropdowns(self):
        self._login_tp()
        for pair in ('yes:yes', 'no:no_contact'):
            self._set(pair)
            match, practice = pair.split(':')
            with self._presence():
                tree = self._page(self.team_url)
            for scope in ('dash', 'roster'):
                row = self._row(tree, scope)
                toggles = self._toggles(row)
                self.assertEqual(sorted(toggles), ['match', 'practice'], scope)
                for key, value in (('match', match), ('practice', practice)):
                    button = toggles[key]
                    self.assertEqual(button.get('aria-haspopup'), 'menu')
                    self.assertIn('o_sc_chip_%s' % TONES[value], button.get('class'), (scope, key))
                    wrap = button.getparent()
                    self.assertIn('o_sc_pill_select_compact', wrap.get('class'))
                    # Short label on the face, the full value as the title.
                    text = ' '.join(button.xpath('.//*[contains(@class, "o_sc_pill_text")]//text()')).strip()
                    self.assertEqual(text, {'match': 'Match', 'practice': 'Practice'}[key])
                    self.assertIn(':', button.get('title'))
                    self.assertTrue(button.xpath('.//*[local-name()="svg"]'), 'no chevron')
                    self.assertEqual(len(self._menu(tree, button)), 1)
                # The pills sit above the stretched link, never inside an <a>.
                self.assertFalse(row.xpath('.//a//button'))
        tree = self._page('/my/players')
        toggles = self._toggles(self._row(tree, 'players'))
        self.assertEqual(sorted(toggles), ['match', 'practice'])

    # -- AC-2 ------------------------------------------------------------
    def test_coach_cards_stay_read_only(self):
        self._login_coach()
        self._set('no:no')
        with self._presence():
            tree = self._page(self.team_url)
        for scope in ('dash', 'roster'):
            row = self._row(tree, scope)
            self.assertFalse(row.xpath('.//*[contains(@class, "o_sc_pill_select")]'), scope)
            self.assertFalse(row.xpath('.//*[@data-sc-pill-select]'), scope)
            pills = row.xpath('.//*[contains(@class, "o_sc_row_status")]/span[contains(@class, "o_sc_status_pill")]')
            self.assertEqual(len(pills), 2, scope)
            for pill in pills:
                self.assertIn('o_sc_chip_red', pill.get('class'))
        self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_pill_popup")]'))
        tree = self._page('/my/players')
        self.assertFalse(self._row(tree, 'players').xpath('.//*[contains(@class, "o_sc_pill_select")]'))

    # -- AC-3 ------------------------------------------------------------
    def test_menu_ids_unique_per_row_scope(self):
        self._login_tp()
        with self._presence():
            tree = self._page(self.team_url)
        ids = tree.xpath('//@id')
        self.assertEqual(len(ids), len(set(ids)), 'duplicate ids on the team page')
        controls = tree.xpath('//button[contains(@class, "o_sc_pill_select")]/@aria-controls')
        self.assertGreaterEqual(len(controls), 6)  # 2 players on the roster + the dashboard card
        for control in controls:
            self.assertEqual(len(tree.xpath('//*[@id="%s"]' % control)), 1, control)
        dash = self._toggles(self._row(tree, 'dash'))['match'].get('aria-controls')
        roster = self._toggles(self._row(tree, 'roster'))['match'].get('aria-controls')
        self.assertNotEqual(dash, roster)
        self.assertIn('dash', dash)
        self.assertIn('roster', roster)

    # -- AC-4 ------------------------------------------------------------
    def test_invalid_choices_greyed_on_cards(self):
        self._login_tp()
        self._set('yes:yes')
        tree = self._page(self.team_url)
        toggles = self._toggles(self._row(tree, 'roster'))
        popup = self._menu(tree, toggles['practice'])[0]
        state = {}
        for item in popup.xpath('.//*[@role="menuitemradio"]'):
            hint = ' '.join(item.xpath('.//*[contains(@class, "o_sc_pill_hint")]//text()')).strip()
            if item.get('aria-disabled') == 'true':
                self.assertTrue(hint)
                self.assertFalse(item.get('data-sc-pill-post'))
                state[item.get('data-sc-pill-value')] = None
            else:
                state[item.get('data-sc-pill-value')] = item.get('data-sc-pill-post')
        self.assertEqual(state, {'yes': 'yes:yes', 'no_contact': None, 'no': None})

    # -- AC-5 ------------------------------------------------------------
    def test_row_fragment_keys(self):
        self._login_tp()
        with self._presence():
            tree = self._page(self.team_url)
        keys = tree.xpath('//*[@data-sc-fragment]/@data-sc-fragment')
        self.assertEqual(len(keys), len(set(keys)), 'duplicate fragment keys')
        for scope in ('dash', 'roster'):
            row = self._row(tree, scope)
            node = self._node(tree, self._key(scope))
            self.assertIsNotNone(node, scope)
            self.assertTrue(node.xpath('ancestor::*[@data-sc-player-id="%s"]' % self.player.id))
            self.assertIn('o_sc_link_row', node.get('class'))
            self.assertEqual(node.get('data-sc-fragment-keep'), '1')
            # Pills, dot and lines inside; the lazy detail outside.
            self.assertEqual(len(self._toggles(node)), 2)
            self.assertTrue(node.xpath('.//*[contains(@class, "o_sc_dot")]'))
            self.assertFalse(node.xpath('.//*[@data-sc-row-detail]'))
            self.assertTrue(row.xpath('./*[@data-sc-row-detail]'))
        with self._presence():
            self.assertFragmentMatchesPage(self.team_url, self._key('roster'))
        self.assertFragmentMatchesPage('/my/players', self._key('players'))

    def test_save_refreshes_every_card_in_place(self):
        self._login_tp()
        self._set('yes:yes')
        payload = self._saved(self.player, 'sc_status', 'no:no')
        for scope in ('dash', 'roster'):
            self.assertRefreshes(payload, self._key(scope))
        self.player.invalidate_recordset()
        with self._presence():
            answer = self._fragments(self.team_url, [self._key('dash'), self._key('roster')])
        self.assertFalse(answer['missing'])
        for scope in ('dash', 'roster'):
            node = lxml_html.fragment_fromstring(answer['fragments'][self._key(scope)])
            for key, button in self._toggles(node).items():
                self.assertIn('o_sc_chip_red', button.get('class'), (scope, key))
            self.assertTrue(node.xpath('.//*[contains(@class, "o_sc_dot") and contains(@class, "o_sc_tone_red")]'))
            self.assertTrue(node.xpath('.//*[@data-sc-row-return]'), 'no « Retour prévu » line')
            wrap = node.xpath('.//*[@data-sc-pill-select]')[0]
            self.assertEqual(wrap.get('data-sc-write-date'), payload['write_date'])
            self.assertEqual(wrap.get('data-sc-old-value'), 'no:no')

    # -- AC-6 ------------------------------------------------------------
    def test_locked_players_row_stays_static(self):
        self._login_tp()
        tree = self._page('/my/players?last_name=Two')
        locked = tree.xpath('//*[@data-sc-row-locked][@data-sc-player-id="%s"]' % self.player_b.id)
        self.assertTrue(locked)
        self.assertFalse(locked[0].xpath('.//*[contains(@class, "o_sc_pill_select")]'))
        self.assertFalse(locked[0].xpath('.//*[@data-sc-fragment]'))
        self.assertEqual(len(locked[0].xpath('.//span[contains(@class, "o_sc_status_pill")]')), 2)

    # -- AC-7 ------------------------------------------------------------
    def test_selection_labels_once_per_request(self):
        Patient = type(self.env['sports.patient'])
        original = Patient._sc_status_labels
        calls = []

        def counting(records):
            calls.append(1)
            return original(records)

        self.env['sports.patient'].create([{
            'first_name': 'Syn%s' % i, 'last_name': 'Roster',
            'team_ids': [Command.set([self.team_a.id])]} for i in range(10)])
        self._login_tp()
        for url in (self.team_url, '/my/players'):
            calls.clear()
            with patch.object(Patient, '_sc_status_labels', counting):
                self._page(url)
            self.assertEqual(len(calls), 1, url)

    def test_model_helpers_take_cached_labels(self):
        labels = self.player._sc_status_labels()
        self.assertEqual(sorted(labels), ['match_status', 'practice_status'])
        Field = type(self.player._fields['match_status'])
        with patch.object(Field, '_description_selection', side_effect=AssertionError('recomputed')):
            pills = self.player._sc_status_pills(labels)
            status = self.player._sc_row_status(labels)
        self.assertEqual([p['key'] for p in pills], ['match', 'practice'])
        self.assertEqual(len(status['pills']), 2)
        self.assertEqual(pills, self.player._sc_status_pills())
        self.assertEqual(status, self.player._sc_row_status())

    # -- AC-8 ------------------------------------------------------------
    def test_tour(self):
        self._set('yes:yes')
        with self._presence():
            self.start_tour(self.team_url + '&tab=players', 'sc_1634_card_pills', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('no', 'yes'))

    def test_tour_coach(self):
        with self._presence():
            self.start_tour(self.team_url + '&tab=players', 'sc_1634_card_pills_coach',
                            login='pc.coach@example.com')

