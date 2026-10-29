"""Task 1624 — the round-1 dashboard widgets on synthetic multi-team
fixtures (dashboard_common_1624). Synthetic fixtures only.

Acceptance criteria:

* UC-W0 /my/home renders the enabled sections in the layout's order with
  their (custom) titles; a switched-off section is not rendered; « Mes
  équipes » is no longer on the home; the classic home (?classic=1) is
  untouched; the header links to « Configurer ».
* UC-W1 Aujourd'hui: my events of the day (a therapist: assigned; a coach:
  my teams'), time + kind + name + venue; never a cancelled one; the live
  « Cliniques aujourd'hui » chip for therapists only.
* UC-W2 À faire: my overdue / today activities — the SAME count as the app
  bar clock's badge (one shared domain); injuries to verify (therapist);
  pending removal requests where the user may act (therapist of the team);
  « Dépassé » returns (therapist, review round 1); the kinds filter hides a
  kind; a coach never gets the therapist lines.
* UC-W3 Changements récents: the recent-change cards of every scoped team
  (one list, team links on each card), the change detail behind
  « Details »; a single-team scope offers « Historique ».
* UC-W4 Joueurs à surveiller: red / yellow players of the scope not in the
  recent changes; « Rouge seulement » keeps the red ones; each player once.
* UC-W5 Annonces: the standing, non-expired announcements of the scope,
  the team's name on each; another team's never.
* UC-W6 Indicateurs: Blessés / En reprise / Disponibles over the scope's
  players, each player once (a player on two teams counts once).
* UC-W7 Couvertures à venir: assigned (therapist) / my teams' (coach)
  events in the next N days (7 / 14 / 30, default the system setting);
  never cancelled.
* UC-W8 Medical rules: a coach's card carries only the yellow / red
  medical pills (never the grey « not filled in » ones a therapist sees);
  a hidden-from-coaches injury is never listed to a coach.
* UC-W9 Multi-instance: a second « Joueurs à surveiller » scoped to one
  team with a custom title renders after the first, with that team's
  players only.
"""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common


@tagged('post_install', '-at_install')
class TestDashboardWidgets1624(Dashboard1624Common):

    def _presence(self, players):
        return patch.object(
            type(self.env['sports.patient']), '_dashboard_card_presence',
            return_value={'players': set(players.ids), 'injuries': set()})

    def _stamp(self, players):
        now = fields.Datetime.now()
        players.sudo().write({'dashboard_last_activity_tp': now,
                              'dashboard_last_activity_coach': now})

    def _player_ids(self, node):
        return [int(i) for i in node.xpath('.//*[@data-sc-player-id]/@data-sc-player-id')]

    # -- UC-W0 ---------------------------------------------------------------
    def test_sections_order_titles_and_no_my_teams(self):
        dash = self._dash(self.tp)
        dash._sc_layout_move('coverage', -1)
        dash._sc_layout_update('today', enabled=False)
        dash._sc_layout_update('todo', title='Synthetic chores')
        self._login_tp()
        text, tree = self._get('/my/home')
        ids = [s.get('data-sc-instance') for s in self._sections(tree)]
        # Review round 1: the new default order (Indicateurs second).
        self.assertEqual(ids, ['indicators', 'todo', 'recent_changes', 'watch', 'followed', 'coverage',
                               'announcements', 'missing_timesheets'])
        title = self._section(tree, 'todo').xpath('.//*[contains(@class, "o_sc_dw_title_text")]')[0]
        self.assertEqual(title.text_content().strip(), 'Synthetic chores')
        self.assertNotIn('My teams', text)
        self.assertFalse(tree.xpath('//a[@data-sc-team-id]'))
        self.assertTrue(tree.xpath('//a[@data-sc-action="dashboard.configure"]'
                                   '[@href="/my/app/dashboard/configure"]'))
        text, _tree = self._get('/my/home?classic=1')
        self.assertIn('o_portal_my_home', text)

    # -- UC-W1 ---------------------------------------------------------------
    def test_today(self):
        self.ev_today.venue_id = self.env['res.partner'].create({
            'name': 'Synthetic Arena', 'is_company': True, 'is_venue': True})
        self._login_tp()
        _text, tree = self._get('/my/home')
        today = self._section(tree, 'today')
        ids = [int(i) for i in today.xpath('.//*[@data-sc-event-id]/@data-sc-event-id')]
        self.assertEqual(ids, [self.ev_today.id])
        self.assertIn('Synthetic Arena', today.text_content())
        self.assertTrue(today.xpath('.//*[@data-sc-section="home.clinic_teaser"]//*[@data-sc-live-count-url]'))
        self._login_coach()
        _text, tree = self._get('/my/home')
        today = self._section(tree, 'today')
        ids = [int(i) for i in today.xpath('.//*[@data-sc-event-id]/@data-sc-event-id')]
        self.assertEqual(ids, [self.ev_today.id])
        self.assertFalse(today.xpath('.//*[@data-sc-section="home.clinic_teaser"]'))

    # -- UC-W2 ---------------------------------------------------------------
    def test_todo_activities_match_clock_badge(self):
        Activity = self.env['mail.activity']
        today = fields.Date.context_today(self.tp)
        model = self.env['ir.model']._get('sports.patient').id
        for deadline in (today - timedelta(days=2), today - timedelta(days=1), today,
                         today + timedelta(days=3)):
            Activity.create({'res_model_id': model, 'res_id': self.red.id,
                             'user_id': self.tp.id, 'summary': 'Synthetic chore',
                             'date_deadline': deadline})
        self._login_tp()
        badge = json.loads(self.url_open('/my/activities/overdue/count').text)['count']
        _text, tree = self._get('/my/home')
        todo = self._section(tree, 'todo')
        overdue = todo.xpath('.//*[@data-sc-todo="activities_overdue"]//*[contains(@class, "o_sc_chip")]')
        self.assertEqual(int(overdue[0].text_content()), badge)
        self.assertGreaterEqual(badge, 2)
        due = todo.xpath('.//*[@data-sc-todo="activities_today"]//*[contains(@class, "o_sc_chip")]')
        self.assertGreaterEqual(int(due[0].text_content()), 1)

    def test_todo_team_lines(self):
        injury = self.env['sports.patient.injury'].create({
            'patient_id': self.yellow.id, 'diagnosis': 'Synthetic tweak'})
        injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        far_injury = self.env['sports.patient.injury'].create({
            'patient_id': self.player_b.id, 'diagnosis': 'Not ours'})
        far_injury.with_context(mail_notrack=True).write({'stage': 'unverified'})
        self.red.sudo().write({'pending_removal': True, 'pending_removal_team_id': self.team_a.id})
        self.shared.sudo().with_context(**{PAST_RETURN_OK: True}).write(
            {'predicted_return_date': fields.Date.today() - timedelta(days=2)})
        self._login_tp()
        _text, tree = self._get('/my/home')
        todo = self._section(tree, 'todo')
        verify = todo.xpath('.//*[@data-sc-todo="verify"]')[0]
        self.assertIn('Synthetic tweak', verify.text_content())
        self.assertNotIn('Not ours', verify.text_content())
        removals = todo.xpath('.//*[@data-sc-todo="removals"]')[0]
        self.assertIn('Synth, Red', removals.text_content())
        returns = todo.xpath('.//*[@data-sc-todo="returns"]')[0]
        self.assertIn('Synth, Shared', returns.text_content())
        # The kinds filter hides a kind.
        self._dash(self.tp)._sc_layout_update('todo', settings={'kinds': ['returns']})
        _text, tree = self._get('/my/home')
        todo = self._section(tree, 'todo')
        self.assertFalse(todo.xpath('.//*[@data-sc-todo="verify"]'))
        self.assertTrue(todo.xpath('.//*[@data-sc-todo="returns"]'))
        # A coach: no therapist lines (review round 1: the overdue returns
        # are a therapist line too — they update those dates).
        self._login_coach()
        _text, tree = self._get('/my/home')
        todo = self._section(tree, 'todo')
        self.assertFalse(todo.xpath('.//*[@data-sc-todo="verify"]'))
        self.assertFalse(todo.xpath('.//*[@data-sc-todo="removals"]'))
        self.assertFalse(todo.xpath('.//*[@data-sc-todo="returns"]'))

    def test_removals_only_where_user_may_act(self):
        # Coach role on Team C only for the itp: not a removal role there.
        self.env['sports.team.staff'].create({
            'team_id': self.team_c.id, 'partner_id': self.itp.partner_id.id, 'role': 'coach'})
        self.yellow.sudo().write({'pending_removal': True, 'pending_removal_team_id': self.team_c.id})
        teams = self.team_a | self.team_c
        Patient = self.env['sports.patient'].with_user(self.itp)
        self.assertEqual(Patient._sc_teams_may_remove(teams), self.team_a)
        for team in teams:
            self.assertEqual(Patient._may_remove_from_team(team), team in self.team_a)
        data = self._dash(self.itp)._sc_data_todo(teams, ['removals'])
        self.assertFalse(data['removals'])

    # -- UC-W3 ---------------------------------------------------------------
    def test_recent_changes_union(self):
        changed = self.red | self.yellow
        self._stamp(changed)
        self._login_tp()
        with self._presence(changed):
            _text, tree = self._get('/my/home')
        section = self._section(tree, 'recent_changes')
        self.assertEqual(set(self._player_ids(section)), set(changed.ids))
        detail = section.xpath('.//*[@data-sc-player-id="%s"]//*[@data-sc-row-detail]/@data-sc-lazy-url'
                               % self.yellow.id)[0]
        self.assertIn('/my/player/%s/recent-changes?detail=1' % self.yellow.id, detail)
        self.assertTrue(section.xpath('.//*[@data-sc-player-id="%s"]//a[@data-sc-row-link]' % self.yellow.id))
        self.assertFalse(section.xpath('.//a[@data-sc-action="dashboard.history"]'))
        # One team in scope: « History » (its digest list).
        self._dash(self.tp)._sc_layout_update(
            'recent_changes', settings={'scope_team_ids': [self.team_c.id]})
        with self._presence(changed):
            _text, tree = self._get('/my/home')
        section = self._section(tree, 'recent_changes')
        self.assertEqual(self._player_ids(section), [self.yellow.id])
        self.assertEqual(section.xpath('.//a[@data-sc-action="dashboard.history"]/@href'),
                         ['/my/team/%s/digest-history' % self.team_c.id])

    # -- UC-W4 ---------------------------------------------------------------
    def test_watch(self):
        self._stamp(self.red)
        self._login_tp()
        with self._presence(self.red):
            _text, tree = self._get('/my/home')
        ids = self._player_ids(self._section(tree, 'watch'))
        # Red / yellow, not the changed one, each once, red first.
        self.assertEqual(ids, [self.shared.id, self.yellow.id])
        self._dash(self.tp)._sc_layout_update('watch', settings={'level': 'red'})
        with self._presence(self.red):
            _text, tree = self._get('/my/home')
        self.assertEqual(self._player_ids(self._section(tree, 'watch')), [self.shared.id])

    # -- UC-W5 ---------------------------------------------------------------
    def test_announcements(self):
        self._login_coach()
        _text, tree = self._get('/my/home')
        section = self._section(tree, 'announcements')
        self.assertEqual([int(i) for i in section.xpath('.//*[@data-sc-team-id]/@data-sc-team-id')],
                         [self.team_a.id])
        text = section.text_content()
        self.assertIn('PC Team A', text)
        self.assertIn('Synthetic standing note A', text)
        self.assertNotIn('expired note C', text)
        self.assertNotIn('not ours', text)

    # -- UC-W6 ---------------------------------------------------------------
    def test_indicators_dedupe(self):
        self.assertEqual(self._dash(self.tp)._sc_data_indicators(self.team_a | self.team_c),
                         {'no_play': 2, 'practice_ok': 1, 'healthy': 1})
        self._login_coach()
        _text, tree = self._get('/my/home')
        values = [v.text_content().strip() for v in self._section(tree, 'indicators').xpath(
            './/*[contains(@class, "o_sc_stat_value")]')]
        self.assertEqual(values, ['2', '1', '1'])

    def test_clinic_admin_indicators_default_to_staffed(self):
        # Team B's red player is not counted by default ...
        self.assertEqual(self._dash(self.cadmin)._sc_data_indicators(
            self._dash(self.cadmin)._sc_scope_teams({})), {'no_play': 2, 'practice_ok': 0, 'healthy': 1})
        # ... only when the admin scopes to it.
        self._dash(self.cadmin)._sc_layout_update(
            'indicators', settings={'scope_team_ids': [self.team_b.id]})
        self._login_cadmin()
        _text, tree = self._get('/my/home')
        values = [v.text_content().strip() for v in self._section(tree, 'indicators').xpath(
            './/*[contains(@class, "o_sc_stat_value")]')]
        self.assertEqual(values, ['1', '0', '0'])

    # -- UC-W7 ---------------------------------------------------------------
    def _coverage_ids(self, tree):
        return [int(i) for i in self._section(tree, 'coverage').xpath(
            './/*[@data-sc-event-id]/@data-sc-event-id')]

    def test_coverage(self):
        self._login_tp()
        _text, tree = self._get('/my/home')
        self.assertEqual(self._coverage_ids(tree), [self.ev_soon.id])
        self._dash(self.tp)._sc_layout_update('coverage', settings={'days': 30})
        _text, tree = self._get('/my/home')
        self.assertEqual(self._coverage_ids(tree), [self.ev_soon.id, self.ev_far.id])
        self.assertIn('30', self._section(tree, 'coverage').xpath(
            './/*[contains(@class, "o_sc_section_sub")]')[0].text_content())
        # Scoped to Team C: only its events.
        self._dash(self.tp)._sc_layout_update('coverage', settings={'scope_team_ids': [self.team_c.id]})
        _text, tree = self._get('/my/home')
        self.assertEqual(self._coverage_ids(tree), [self.ev_far.id])
        # A coach: my teams' events (not Team B's), never cancelled.
        self._login_coach()
        _text, tree = self._get('/my/home')
        self.assertEqual(self._coverage_ids(tree), [self.ev_soon.id])

    # -- UC-W8 ---------------------------------------------------------------
    def test_coach_medical_rules(self):
        self._stamp(self.red)
        hidden = self.env['sports.patient.injury'].create({
            'patient_id': self.yellow.id, 'diagnosis': 'Synthetic hidden thing',
            'hidden_from_coaches': True})
        hidden.with_context(mail_notrack=True).write({'stage': 'unverified'})
        self._login_tp()
        with self._presence(self.red):
            _text, tree = self._get('/my/home')
        self.assertTrue(tree.xpath('//section[@data-sc-instance="watch"]'
                                   '//*[@data-sc-med-level="unset"]'))
        self._login_coach()
        with self._presence(self.red):
            text, tree = self._get('/my/home')
        self.assertFalse(tree.xpath('//*[@data-sc-med-level="unset"]'))
        self.assertNotIn('Synthetic hidden thing', text)

    # -- UC-W9 ---------------------------------------------------------------
    def test_second_watch_instance(self):
        dash = self._dash(self.tp)
        new_id = dash._sc_layout_add('watch')
        dash._sc_layout_update(new_id, title='Watch C only',
                               settings={'scope_team_ids': [self.team_c.id]})
        dash._sc_layout_move(new_id, -1)
        self._login_tp()
        _text, tree = self._get('/my/home')
        ids = [s.get('data-sc-instance') for s in self._sections(tree)]
        self.assertEqual(ids.index(new_id), ids.index('missing_timesheets') - 1)
        self.assertLess(ids.index('watch'), ids.index(new_id))
        second = self._section(tree, new_id)
        self.assertIn('Watch C only', second.text_content())
        self.assertIn('DB Team C', second.xpath('.//*[@data-sc-dw-scope]')[0].text_content())
        self.assertEqual(sorted(self._player_ids(second)), sorted((self.shared | self.yellow).ids))
        # Row fragments / detail ids stay unique on the page.
        frags = tree.xpath('//*[@data-sc-fragment]/@data-sc-fragment')
        self.assertEqual(len(frags), len(set(frags)))
