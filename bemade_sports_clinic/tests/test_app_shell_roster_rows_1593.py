"""Task 1593 (portal app P3) — player rows carry the legacy card's content:
team names as links, training recommendation, predicted return and an
expandable active-injury detail. Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 A player row (team roster, « Other players to watch », /my/players)
  is a link row: the name opens the player page; the training
  recommendation shows on ONE line; an injured player shows « Retour prévu »
  (the date, « — » when unset), a healthy one does not; a « Details »
  control expands a region under the row, lazy-loaded from
  /my/player/<id>/row-detail (never rendered for every row).
* UC-2 Team names: on /my/players the player's teams are separate links to
  the team page — a link only for a team the viewer may open (else plain
  text); on a team's own page (roster / watch lists) there are no team
  links, as on the legacy card. The player page hero's team names are
  links too.
* UC-3 Expanded detail: the whole training recommendation, predicted
  return, last consultation and the active injuries. A coach never gets an
  injury hidden from coaches nor an internal note (Loi 25) — neither in the
  row nor in the detail; a therapist sees both, as on the legacy card.
* UC-4 The detail route is access-checked like the player page: a viewer
  who may not open the player gets a 403 and no data.
* UC-5 No per-row queries: the team page and the players list cost about
  the same number of queries for a 5-player and a 40-player roster.
* UC-6 (tour, phone width) « Details » opens the injury detail under the
  row, without leaving the page, and closes it again.
* UC-7 French (fr_CA): « Retour prévu : », « Détails » on the row and
  « Aucune blessure active. » in the detail render translated.
"""
import logging
from datetime import date

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

_logger = logging.getLogger(__name__)


def _text(node):
    return ' '.join(node.text_content().split())


class Rows1593Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # The player is on team A (staffed by the coach and the therapist)
        # and team C (staffed by nobody here).
        cls.team_c = env['sports.team'].create({'name': 'PC Team C', 'parent_id': cls.org.id})
        cls.player.write({
            'team_ids': [Command.set([cls.team_a.id, cls.team_c.id])],
            'training_recommendation': 'Synthetic bike only\nSecond line of advice',
            'predicted_return_date': date(2026, 3, 15),
            'last_consultation_date': date(2026, 2, 1),
            'match_status': 'no',
            'practice_status': 'no',
        })
        cls.injury.sudo().write({
            'external_notes': 'Synthetic external note',
            'internal_notes': 'Synthetic internal note',
        })
        cls.hidden_injury = env['sports.patient.injury'].create({
            'patient_id': cls.player.id,
            'diagnosis': 'Synthetic hidden diagnosis',
            'hidden_from_coaches': True,
        })
        cls.hidden_injury.with_context(mail_notrack=True).write({'stage': 'active'})
        cls.healthy = env['sports.patient'].create({
            'first_name': 'Hal', 'last_name': 'Healthy',
            'team_ids': [Command.set([cls.team_a.id])],
        })
        cls.team_url = '/my/team?team_id=%s' % cls.team_a.id

    @staticmethod
    def _row(tree, section, player):
        rows = tree.xpath('//*[@data-sc-section="%s"]//*[contains(@class, "o_sc_player_row")]'
                          '[@data-sc-player-id="%s"]' % (section, player.id))
        return rows[0] if rows else None

    @staticmethod
    def _team_links(row):
        return [(a.get('href'), _text(a))
                for a in row.xpath('.//a[contains(@class, "o_sc_row_link")]')]

    @staticmethod
    def _plain_teams(row):
        return [_text(s) for s in row.xpath('.//*[contains(@class, "o_sc_row_link_plain")]')]

    def _detail(self, row):
        region = row.xpath('.//*[@data-sc-row-detail]')
        self.assertTrue(region, 'no expandable detail region')
        url = region[0].get('data-sc-lazy-url')
        resp = self.url_open(url)
        return resp, url


@tagged('post_install', '-at_install')
class TestAppShellRosterRows1593(Rows1593Common):

    # -- UC-1 ------------------------------------------------------------
    def test_roster_row_content(self):
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get(self.team_url)
        row = self._row(tree, 'team.roster', self.player)
        self.assertIsNotNone(row)
        # One main link, to the player page with the team context.
        main = row.xpath('.//a[contains(@class, "o_sc_link_row_main")]')
        self.assertEqual(len(main), 1)
        self.assertEqual(main[0].get('href'), '/my/player?player_id=%s&team_id=%s'
                         % (self.player.id, self.team_a.id))
        # No <a> inside an <a>.
        self.assertFalse(row.xpath('.//a//a'))
        training = row.xpath('.//*[@data-sc-row-training]')
        self.assertEqual(_text(training[0]), 'Synthetic bike only Second line of advice')
        ret = row.xpath('.//*[@data-sc-row-return]')
        self.assertTrue(ret)
        self.assertIn('03/15/2026', _text(ret[0]))
        # The detail is NOT rendered with the page: a lazy region + control.
        self.assertNotIn('Synthetic external note', _text(row))
        button = row.xpath('.//button[@data-sc-row-expand]')
        region = row.xpath('.//*[@data-sc-row-detail]')
        self.assertEqual(button[0].get('aria-controls'), region[0].get('id'))
        self.assertEqual(region[0].get('hidden'), 'hidden')
        self.assertEqual(region[0].get('data-sc-lazy-url'),
                         '/my/player/%s/row-detail?team_id=%s' % (self.player.id, self.team_a.id))
        # A healthy player: no « Retour prévu », no training line.
        healthy = self._row(tree, 'team.roster', self.healthy)
        self.assertFalse(healthy.xpath('.//*[@data-sc-row-return]'))
        self.assertFalse(healthy.xpath('.//*[@data-sc-row-training]'))

    def test_unset_return_date_shows_dash(self):
        self.player.write({'predicted_return_date': False})
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get('/my/players')
        ret = self._row(tree, 'players.list', self.player).xpath('.//*[@data-sc-row-return]')
        self.assertTrue(_text(ret[0]).endswith('—'))

    def test_detail_ids_unique_when_listed_twice(self):
        """The same player on the watch list and the roster: two regions,
        two ids."""
        self.player.sudo().write({'dashboard_last_activity_tp': False,
                                  'dashboard_last_activity_coach': False})
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get(self.team_url)
        self.assertIsNotNone(self._row(tree, 'team.watchlist', self.player))
        ids = tree.xpath('//*[@data-sc-row-detail]/@id')
        self.assertEqual(len(ids), len(set(ids)))

    # -- UC-2 ------------------------------------------------------------
    def test_players_list_team_links(self):
        self._switch(True)
        self._login_coach()
        _text_, tree = self._get('/my/players')
        row = self._row(tree, 'players.list', self.player)
        # Team A (staffed) is a link; team C (not staffed) plain text.
        self.assertEqual(self._team_links(row),
                         [('/my/team?team_id=%s' % self.team_a.id, 'PC Team A')])
        self.assertEqual(self._plain_teams(row), ['PC Team C'])
        self.assertEqual(row.xpath('.//*[@data-sc-row-detail]/@data-sc-lazy-url'),
                         ['/my/player/%s/row-detail' % self.player.id])

    def test_team_page_rows_have_no_team_links(self):
        self.player.sudo().write({'dashboard_last_activity_tp': False,
                                  'dashboard_last_activity_coach': False})
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get(self.team_url)
        for section in ('team.roster', 'team.watchlist'):
            row = self._row(tree, section, self.player)
            self.assertIsNotNone(row, section)
            self.assertFalse(row.xpath('.//*[contains(@class, "o_sc_row_link")]'), section)

    def test_hero_team_links(self):
        self._switch(True)
        self._login_coach()
        _text_, tree = self._get('/my/player?player_id=%s' % self.player.id)
        hero = tree.xpath('//*[@data-sc-hero-teams]')[0]
        self.assertEqual(hero.xpath('.//a/@href'), ['/my/team?team_id=%s' % self.team_a.id])
        self.assertEqual(_text(hero), 'PC Team A, PC Team C')

    # -- UC-3 ------------------------------------------------------------
    def test_coach_detail_hides_hidden_injury_and_internal_note(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get(self.team_url)
        self.assertNotIn('Synthetic hidden diagnosis', text)
        self.assertNotIn('Synthetic internal note', text)
        resp, _url = self._detail(self._row(tree, 'team.roster', self.player))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Sprain', resp.text)
        self.assertIn('Synthetic external note', resp.text)
        self.assertNotIn('Synthetic hidden diagnosis', resp.text)
        self.assertNotIn('Synthetic internal note', resp.text)
        # The whole training recommendation + the last consultation.
        detail = lxml_html.fromstring(resp.text)
        self.assertIn('Second line of advice',
                      _text(detail.xpath('//*[@data-sc-row-detail-section="training"]')[0]))
        self.assertIn('02/01/2026', _text(detail))
        self.assertEqual(detail.xpath('//a[contains(@class, "o_sc_section_more")]/@href'),
                         ['/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)])

    def test_therapist_detail_shows_what_legacy_showed(self):
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get('/my/players')
        resp, _url = self._detail(self._row(tree, 'players.list', self.player))
        self.assertEqual(resp.status_code, 200)
        for expected in ('Sprain', 'Synthetic hidden diagnosis', 'Synthetic external note',
                         'Synthetic internal note', 'Second line of advice'):
            self.assertIn(expected, resp.text)

    def test_healthy_player_detail_has_no_injury(self):
        self._switch(True)
        self._login_tp()
        resp = self.url_open('/my/player/%s/row-detail' % self.healthy.id)
        self.assertEqual(resp.status_code, 200)
        tree = lxml_html.fromstring(resp.text)
        self.assertTrue(tree.xpath('//*[@data-sc-row-detail-section="no_injury"]'))
        self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_injury_detail")]'))

    # -- UC-4 ------------------------------------------------------------
    def test_detail_access_checked(self):
        self.player_b.sudo().write({'training_recommendation': 'Synthetic secret plan'})
        self._switch(True)
        for login in (self._login_coach, self._login_plain):
            login()
            resp = self.url_open('/my/player/%s/row-detail' % self.player_b.id)
            self.assertEqual(resp.status_code, 403)
            self.assertNotIn('Synthetic secret plan', resp.text)
        # A foreign team id never becomes the context.
        self._login_coach()
        resp = self.url_open('/my/player/%s/row-detail?team_id=%s' % (self.player.id, self.team_b.id))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('team_id=%s' % self.team_b.id, resp.text)


@tagged('post_install', '-at_install')
class TestAppShellRosterRowsQueries1593(AppShellCommon):
    """UC-5: the rows' content is computed for the whole list at once."""

    def _fill(self, team, count, start):
        env = self.env
        other = env['sports.team'].create({'name': 'PC Extra %s' % start, 'parent_id': self.org.id})
        for n in range(count):
            player = env['sports.patient'].create({
                'first_name': 'Synthetic', 'last_name': 'Perf %03d' % (start + n),
                'team_ids': [Command.set([team.id, other.id])],
                'training_recommendation': 'Synthetic advice %s' % n,
                'predicted_return_date': date(2026, 5, 1),
                'match_status': 'no', 'practice_status': 'no',
            })
            injury = env['sports.patient.injury'].create({
                'patient_id': player.id, 'diagnosis': 'Synthetic perf %s' % n,
            })
            injury.with_context(mail_notrack=True).write({'stage': 'active'})

    def _queries(self, url):
        self.env.flush_all()
        self.env.invalidate_all()
        self.url_open(url)  # warm-up (assets, session, caches)
        self.env.flush_all()
        self.env.invalidate_all()
        before = self.cr.sql_log_count
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200)
        return self.cr.sql_log_count - before

    def test_query_count_bounded(self):
        self._switch(True)
        team_small = self.env['sports.team'].create({'name': 'PC Small', 'parent_id': self.org.id})
        team_big = self.env['sports.team'].create({'name': 'PC Big', 'parent_id': self.org.id})
        for team in (team_small, team_big):
            self.env['sports.team.staff'].create({
                'team_id': team.id, 'partner_id': self.tp.partner_id.id, 'role': 'therapist',
            })
        self._fill(team_small, 5, 0)
        self._fill(team_big, 40, 100)
        self._login_tp()
        small = self._queries('/my/team?team_id=%s' % team_small.id)
        big = self._queries('/my/team?team_id=%s' % team_big.id)
        _logger.info("1593 team page queries: 5 rows %s, 40 rows %s", small, big)
        # 35 more rows, each with an injury, a training recommendation and
        # two teams: a per-row query would add 35+ queries (measured: +0).
        self.assertLess(big - small, 10, 'team page: %s vs %s queries' % (small, big))
        small = self._queries('/my/players?team_id=%s' % team_small.id)
        big = self._queries('/my/players?team_id=%s' % team_big.id)
        _logger.info("1593 players list queries: 5 rows %s, 40 rows %s", small, big)
        self.assertLess(big - small, 10, 'players list: %s vs %s queries' % (small, big))


@tagged('post_install', '-at_install')
class TestAppShellRosterRowsTour1593(Rows1593Common):
    browser_size = '390x844'

    def test_expand_row_detail(self):
        self._switch(True)
        self.start_tour(self.team_url + '&tab=players', 'sc_1593_row_expand',
                        login='pc.coach@example.com')


@tagged('post_install', '-at_install')
class TestAppShellRosterRowsI18n1593(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_rows_in_french(self):
        self.player.write({'match_status': 'no', 'practice_status': 'no'})
        healthy = self.env['sports.patient'].create({
            'first_name': 'Hal', 'last_name': 'Healthy',
            'team_ids': [Command.set([self.team_a.id])],
        })
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr('/my/players'))
        row = tree.xpath('//*[contains(@class, "o_sc_player_row")][@data-sc-player-id="%s"]'
                         % self.player.id)[0]
        self.assertTrue(_text(row.xpath('.//*[@data-sc-row-return]')[0]).startswith('Retour prévu :'))
        self.assertEqual(_text(row.xpath('.//button[@data-sc-row-expand]')[0]), 'Détails')
        text = self._fr('/my/player/%s/row-detail' % healthy.id)
        self.assertIn('Aucune blessure active.', text)
        self.assertIn('Dernière consultation', text)
