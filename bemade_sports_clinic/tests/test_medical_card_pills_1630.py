"""Task 1630, review round 1 (owner UAT 2026-10-22) — the RED medical pills
on player cards across the app. Synthetic fixtures only.

Acceptance criteria:

* (Task 1677: the levels follow the lists — fixtures through set_medical;
  a red pill names its life-threatening items.)
* CARD-1 A player whose allergy and / or medical-alert level is « Urgent –
  life-threatening » shows a compact, static « Allergies » (with the EpiPen
  icon when ticked) and / or « Medical alert » pill in the card's status
  line — on the team dashboard (« Recent changes », « Other players to
  watch »), the team roster and /my/players — for a therapist AND for a
  coach (the owner's rule: a coach sees red).
* CARD-2 The pills sit inside the card's read fragment
  ``sports.patient:<id>:row-<scope>`` (a save refreshes them in place), never
  inside an <a>. Task 1652: each is a button opening the player page's popup
  (``data-sc-med-card-sheet``), rendered ONCE on the page, outside every
  read fragment; the Info tab as the fallback.
* CARD-3 « Not urgent » (yellow), « None » (grey) and « Not specified »
  never show on a card. Superseded by review round 2 (owner 2026-10-27):
  BOTH pills sit inside every card for a therapist, coloured by level —
  red, yellow, grey (none / not filled in) — on their own line under the
  Match / Practice line; a coach keeps the header's rule (yellow / red
  only, owner + MC 2026-10-21).
* CARD-4 A viewer without read access to the fields (the field-group check
  fails) gets no pill and no AccessError.
* CARD-5 The levels are read in ONE batched read for the whole list.
"""
from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_card_status_pills_1634 import CardPills1634Common

MED = './/*[contains(@class, "o_sc_row_status")]/*[@data-sc-med-pill]'


class MedicalCards1630Common(CardPills1634Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Task 1677: the levels follow the lists (synthetic items).
        set_medical(cls.player, allergies=[('Synthetic peanut', True)],
                    conditions=[('Synthetic epilepsy', True)], epipen=True)
        set_medical(cls.other, allergies=[('Synthetic pollen', False)], conditions=[], none_condition=True)

    def _med(self, row):
        return {node.get('data-sc-med-pill'): node for node in row.xpath(MED)}

    def _assert_red(self, row, where, epipen=True):
        pills = self._med(row)
        self.assertEqual(sorted(pills), ['allergy', 'medical_alert'], where)
        for key, node in pills.items():
            self.assertEqual(node.tag, 'button', where)  # task 1652
            for cls_name in ('o_sc_med_pill', 'o_sc_med_urgent', 'o_sc_med_card_pill'):
                self.assertIn(cls_name, node.get('class'), (where, key))
            self.assertIn(':', node.get('title'), (where, key))
            self.assertFalse(node.xpath('ancestor::a | ancestor::button'), (where, key))
            # Inside the row's read fragment (refreshed with the #1634 rows).
            self.assertTrue(node.xpath('ancestor::*[starts-with(@data-sc-fragment, "sports.patient:%s:row-")]'
                                       % self.player.id), (where, key))
        self.assertEqual(bool(pills['allergy'].xpath('.//*[@data-sc-med-epipen]')), epipen, where)
        self.assertFalse(pills['medical_alert'].xpath('.//*[@data-sc-med-epipen]'), where)
        # Task 1654 / 1677: a red pill names its life-threatening items.
        self.assertEqual(' '.join(pills['allergy'].text_content().split()), 'Synthetic peanut', where)
        self.assertEqual(' '.join(pills['medical_alert'].text_content().split()), 'Synthetic epilepsy', where)
        # Task 1652: the popup, once on the page, outside every fragment.
        for key, node in pills.items():
            sheet_id = 'sc_med_card_%s_%s' % (key, self.player.id)
            self.assertEqual(node.get('data-sc-med-card-sheet'), sheet_id, (where, key))
            self.assertEqual(node.get('data-sc-med-fallback'),
                             '/my/player?player_id=%s&tab=info' % self.player.id, (where, key))
            sheets = row.getroottree().xpath('//dialog[@id="%s"]' % sheet_id)
            self.assertEqual(len(sheets), 1, (where, key))
            self.assertFalse(sheets[0].xpath('ancestor::*[@data-sc-fragment]'), (where, key))

    def _all_rows(self, tree, player):
        return tree.xpath('//*[contains(@class, "o_sc_player_row")][@data-sc-player-id="%s"]' % player.id)


@tagged('post_install', '-at_install')
class TestMedicalCardPills1630(MedicalCards1630Common):

    # -- CARD-1 / CARD-2 -------------------------------------------------
    def test_red_pills_on_every_card_tp_and_coach(self):
        for login in (self._login_tp, self._login_coach):
            login()
            with self._presence():
                tree = self._page(self.team_url)
            self._assert_red(self._row(tree, 'dash'), (login.__name__, 'dash'))
            self._assert_red(self._row(tree, 'roster'), (login.__name__, 'roster'))
            self._assert_red(self._row(self._page('/my/players'), 'players'), (login.__name__, 'players'))

    def test_red_pills_on_watch_cards(self):
        self.player.sudo().write({'dashboard_last_activity_tp': False,
                                  'dashboard_last_activity_coach': False,
                                  'match_status': 'no', 'practice_status': 'no',
                                  'allergy_epipen': False})
        for login in (self._login_tp, self._login_coach):
            login()
            tree = self._page(self.team_url)
            rows = tree.xpath('//*[@data-sc-section="team.watchlist"]//*[contains(@class, "o_sc_player_row")]'
                              '[@data-sc-player-id="%s"]' % self.player.id)
            self.assertEqual(len(rows), 1, login.__name__)
            self._assert_red(rows[0], (login.__name__, 'watch'), epipen=False)

    def test_red_and_yellow_for_a_coach(self):
        # Review round 2: a coach sees the yellow one too (never a grey one).
        set_medical(self.player, allergies=[('Synthetic peanut', True)], conditions=[('Synthetic epilepsy', False)])
        self._login_coach()
        with self._presence():
            tree = self._page(self.team_url)
        for scope in ('dash', 'roster'):
            pills = self._med(self._row(tree, scope))
            self.assertEqual(list(pills), ['allergy', 'medical_alert'], scope)
            self.assertIn('o_sc_med_urgent', pills['allergy'].get('class'))
            self.assertIn('o_sc_med_minor', pills['medical_alert'].get('class'))
        set_medical(self.player, allergies=[('Synthetic peanut', True)], conditions=[], none_condition=True)
        with self._presence():
            tree = self._page(self.team_url)
        self.assertEqual(list(self._med(self._row(tree, 'roster'))), ['allergy'])

    def test_pills_refresh_with_the_row_fragment(self):
        self._login_tp()
        key = self._key('roster')
        self.assertFragmentMatchesPage(self.team_url, key)
        item = self.player.sudo().allergy_critical_ids
        resp = self.url_open('/my/app/medical/item/%s/save' % item.id, data={
            'life_threatening': '0', 'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)
        payload = resp.json()
        self.assertRefreshes(payload, key)
        node = self._fragment(self.team_url, key)
        # Review round 2: still both pills, the allergy one now yellow.
        pills = self._med(node)
        self.assertEqual(list(pills), ['allergy', 'medical_alert'])
        self.assertIn('o_sc_med_minor', pills['allergy'].get('class'))
        self.assertIn('o_sc_med_urgent', pills['medical_alert'].get('class'))

    # -- CARD-3 (review round 2) -------------------------------------------
    def test_every_level_in_the_card_for_a_therapist(self):
        for level, tone, state in (
                ('minor', 'o_sc_med_minor', dict(allergies=[('Synthetic peanut', False)],
                                                 conditions=[('Synthetic epilepsy', False)])),
                ('none', 'o_sc_med_none', dict(allergies=[], conditions=[], none_allergy=True, none_condition=True)),
                ('unset', 'o_sc_med_none', dict(allergies=[], conditions=[], none_allergy=False,
                                                none_condition=False))):
            set_medical(self.player, **state)
            self._login_tp()
            with self._presence():
                tree = self._page(self.team_url)
            tree_players = self._page('/my/players')
            rows = self._all_rows(tree, self.player) + self._all_rows(tree_players, self.player)
            self.assertGreaterEqual(len(rows), 3)
            for node in rows:
                pills = self._med(node)
                self.assertEqual(list(pills), ['allergy', 'medical_alert'], level)
                for key, pill in pills.items():
                    self.assertIn(tone, pill.get('class'), (level, key))
                    self.assertEqual(pill.get('data-sc-med-level'), level, (level, key))
                    # Its own line, right under the Match / Practice line.
                    line = pill.getparent()
                    self.assertEqual(line.get('data-sc-row-med'), '1')
                    self.assertIn('o_sc_row_status', line.getprevious().get('class'))
                    # The popup is on the page.
                    self.assertTrue(node.getroottree().xpath('//dialog[@id="%s"]'
                                                             % pill.get('data-sc-med-card-sheet')))
            # A coach: no grey pill (owner + MC 2026-10-21).
            self._login_coach()
            with self._presence():
                tree = self._page(self.team_url)
            for node in self._all_rows(tree, self.player):
                self.assertEqual(bool(node.xpath(MED)), level == 'minor', (level, 'coach'))

    # -- CARD-4 ----------------------------------------------------------
    def test_no_field_access_shows_nothing(self):
        Patient = self.env['sports.patient']
        players = (self.player | self.other)
        self.assertEqual(players.with_user(self.plain)._sc_card_medical_pills(), {})
        # Review round 2: a therapist gets both players (grey included).
        self.assertEqual(sorted(players.with_user(self.tp)._sc_card_medical_pills()),
                         sorted(players.ids))
        # A sudo recordset is still checked as the CURRENT user.
        self.assertEqual(players.with_user(self.plain).sudo()._sc_card_medical_pills(), {})
        # Rendered: the field-group check fails for the viewer -> no pill, no error.
        original = type(Patient)._has_field_access
        medical = {'allergy_level', 'allergy_epipen', 'medical_alert_level'}

        def no_medical(records, field, operation):
            if field.name in medical:
                return False
            return original(records, field, operation)

        self._login_tp()
        with patch.object(type(Patient), '_has_field_access', no_medical), self._presence():
            tree = self._page(self.team_url)
            tree_players = self._page('/my/players')
        rows = self._all_rows(tree, self.player) + self._all_rows(tree_players, self.player)
        self.assertGreaterEqual(len(rows), 3)
        for node in rows:
            self.assertFalse(node.xpath(MED))

    def test_unreadable_record_skipped(self):
        """A record the viewer may not read is dropped, the others still show."""
        stranger = self.env['sports.patient'].create({
            'first_name': 'Syn', 'last_name': 'Stranger',
            'team_ids': [Command.set([self.team_b.id])],
        })
        set_medical(stranger, allergies=[('Synthetic sesame', True)])
        coach_players = (self.player | stranger).with_user(self.coach)
        pills = coach_players._sc_card_medical_pills()
        self.assertIn(self.player.id, pills)
        self.assertNotIn(stranger.id, pills)

    # -- CARD-5 ----------------------------------------------------------
    def test_one_batched_read(self):
        many = self.env['sports.patient'].create([{
            'first_name': 'Syn%s' % i, 'last_name': 'Batch',
            'team_ids': [Command.set([self.team_a.id])],
        } for i in range(12)])
        self.env['sports.patient.critical.item'].with_context(sc_critical_quiet=True).create([{
            'patient_id': player.id, 'family': 'allergy', 'name': 'Synthetic sesame',
            'life_threatening': True} for player in many])

        def queries(records):
            records = records.with_user(self.tp)
            records.invalidate_recordset()
            before = self.env.cr.sql_log_count
            pills = records._sc_card_medical_pills()
            return self.env.cr.sql_log_count - before, pills

        one, _pills = queries(self.player)
        all_, pills = queries(many | self.player)
        self.assertEqual(len(pills), 13)
        self.assertLessEqual(all_, one, 'a per-row read: %s vs %s queries' % (all_, one))
