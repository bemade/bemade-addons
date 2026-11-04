"""Task 1738 — « Suivis ★ » filter on the Joueurs list (/my/players, app shell).

Acceptance criteria (owner-approved plan, 2026-11-02):

* UC1 — a user who may follow players (``patient.follow``: the staff roles)
  sees a « Suivis ★ » chip in the filter bar, OFF by default (not remembered);
  with ``followed=1`` the list holds only the players they follow.
* UC2 — the filter ANDs with the other filters (e.g. a team); the chip link
  toggles it while keeping the other filters; the search form carries it.
* UC3 — the pager (and the sort menu) keep ``followed=1``.
* UC4 — a user who may not follow players (no ``patient.follow``) sees no
  chip and ``followed=1`` is ignored for them (the full list). NB the plan
  said « coach sees no chip », but ``patient.follow`` is STAFF — coaches
  included (they already follow players) — so a coach gets the chip too.
* UC5 — a small filled ★ marks the followed players' rows (for users who may
  follow), only those rows.
* UC6 — chip on, no result: « Vous ne suivez aucun joueur… » when the user
  follows nobody; the usual no-result message when other filters exclude the
  followed players.

Synthetic fixtures only (public repository): see dashboard_common_1624.
"""
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.team_staff_portal import TeamStaffPortal
from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common


@tagged('post_install', '-at_install')
class TestPlayersFollowedFilter1738(Dashboard1624Common):

    def _row_ids(self, tree):
        return sorted(int(i) for i in tree.xpath(
            '//*[@data-sc-section="players.list"]/*[@data-sc-player-id]/@data-sc-player-id'))

    def _chip(self, tree):
        return tree.xpath('//a[@data-sc-action="players.followed"]')

    def _follow_tp(self, *players):
        for player in players:
            player.with_user(self.tp)._sc_follow(True)

    # -- UC1 -----------------------------------------------------------------
    def test_chip_off_by_default_and_filter_lists_followed_only(self):
        self._follow_tp(self.red, self.yellow)
        self._login_tp()
        _text, tree = self._get('/my/players')
        chip = self._chip(tree)
        self.assertEqual(len(chip), 1)
        self.assertEqual(chip[0].get('aria-pressed'), 'false')
        self.assertIn(self.shared.id, self._row_ids(tree))
        _text, tree = self._get('/my/players?followed=1')
        self.assertEqual(self._row_ids(tree), sorted((self.red | self.yellow).ids))
        self.assertEqual(self._chip(tree)[0].get('aria-pressed'), 'true')
        # Not remembered: the bare list is unfiltered again.
        _text, tree = self._get('/my/players')
        self.assertEqual(self._chip(tree)[0].get('aria-pressed'), 'false')
        self.assertIn(self.shared.id, self._row_ids(tree))

    # -- UC2 -----------------------------------------------------------------
    def test_ands_with_team_filter_and_chip_keeps_filters(self):
        self._follow_tp(self.red, self.yellow)
        self._login_tp()
        _text, tree = self._get('/my/players?followed=1&team_id=%s' % self.team_c.id)
        self.assertEqual(self._row_ids(tree), [self.yellow.id])
        # The chip (now on) turns the filter off and keeps the team.
        args = parse_qs(urlparse(self._chip(tree)[0].get('href')).query)
        self.assertEqual(args.get('team_id'), [str(self.team_c.id)])
        self.assertNotIn('followed', args)
        # The search form carries the filter.
        self.assertEqual(tree.xpath('//form[@data-sc-section="players.search"]'
                                    '//input[@name="followed"]/@value'), ['1'])
        # Off: the chip turns it on, keeping the team.
        _text, tree = self._get('/my/players?team_id=%s' % self.team_c.id)
        args = parse_qs(urlparse(self._chip(tree)[0].get('href')).query)
        self.assertEqual(args.get('team_id'), [str(self.team_c.id)])
        self.assertEqual(args.get('followed'), ['1'])
        self.assertFalse(tree.xpath('//form[@data-sc-section="players.search"]'
                                    '//input[@name="followed"]'))

    # -- UC3 -----------------------------------------------------------------
    def test_pager_and_sort_keep_filter(self):
        self._follow_tp(self.red, self.yellow)
        self._login_tp()
        with patch.object(TeamStaffPortal, '_items_per_page', 1):
            _text, tree = self._get('/my/players?followed=1')
            self.assertEqual(len(self._row_ids(tree)), 1)
            page_links = tree.xpath('//*[contains(@class, "o_sc_pager")]//a[contains(@href, "/page/2")]/@href')
            self.assertTrue(page_links)
            for href in page_links:
                self.assertEqual(parse_qs(urlparse(href).query).get('followed'), ['1'])
            _text, tree2 = self._get('/my/players/page/2?followed=1')
        self.assertEqual(len(self._row_ids(tree2)), 1)
        self.assertEqual(sorted(self._row_ids(tree) + self._row_ids(tree2)),
                         sorted((self.red | self.yellow).ids))
        sort_links = tree.xpath('//a[contains(@href, "sort=")]/@href')
        self.assertTrue(sort_links)
        for href in sort_links:
            self.assertEqual(parse_qs(urlparse(href).query).get('followed'), ['1'])

    # -- UC4 -----------------------------------------------------------------
    def test_user_who_may_not_follow_sees_no_chip_and_param_is_ignored(self):
        self.red.with_user(self.coach)._sc_follow(True)
        self._login_coach()
        Patient = type(self.env['sports.patient'])
        with patch.object(Patient, '_sc_follow_allowed', lambda self: False):
            _text, full = self._get('/my/players')
            self.assertFalse(self._chip(full))
            _text, tree = self._get('/my/players?followed=1')
        self.assertFalse(self._chip(tree))
        self.assertEqual(self._row_ids(tree), self._row_ids(full))
        self.assertGreater(len(self._row_ids(tree)), 1)
        self.assertFalse(tree.xpath('//*[@data-sc-row-followed]'))

    def test_coach_may_follow_so_sees_chip(self):
        """Plan premise corrected: ``patient.follow`` is STAFF (coaches
        included — they already have the ★ toggle and the « Joueurs que je
        suis » widget), so the chip follows that same rule."""
        self.assertTrue(self.env['sports.patient'].with_user(self.coach)._sc_follow_allowed())
        self.red.with_user(self.coach)._sc_follow(True)
        self._login_coach()
        _text, tree = self._get('/my/players?followed=1')
        self.assertEqual(len(self._chip(tree)), 1)
        self.assertEqual(self._row_ids(tree), [self.red.id])

    # -- UC5 -----------------------------------------------------------------
    def test_star_on_followed_rows_only(self):
        self._follow_tp(self.red)
        self._login_tp()
        _text, tree = self._get('/my/players')
        starred = [int(i) for i in tree.xpath(
            '//*[@data-sc-player-id][.//*[@data-sc-row-followed]]/@data-sc-player-id')]
        self.assertEqual(starred, [self.red.id])
        self.assertTrue(tree.xpath(
            '//*[@data-sc-player-id="%s"]//*[@data-sc-row-followed]//*[name()="svg"]' % self.red.id))

    # -- UC6 -----------------------------------------------------------------
    def test_empty_states(self):
        self._login_tp()
        _text, tree = self._get('/my/players?followed=1')
        self.assertFalse(self._row_ids(tree))
        self.assertTrue(tree.xpath('//*[@data-sc-empty="players.followed-none"]'))
        # Following someone the other filters exclude: the usual message.
        self._follow_tp(self.red)
        _text, tree = self._get('/my/players?followed=1&team_id=%s' % self.team_c.id)
        self.assertFalse(self._row_ids(tree))
        self.assertFalse(tree.xpath('//*[@data-sc-empty="players.followed-none"]'))
        self.assertIn('No players match these filters.', ' '.join(tree.xpath('//text()')))
