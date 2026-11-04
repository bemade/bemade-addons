"""Task 1650 — the header search (GET /my/app/search, the search sheet).
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 Players by first / last name: accent- and case-insensitive,
  word-prefix (« eloi syn » finds « Synthétique, Éloïse »).
* UC-2 Scopes, like the Joueurs page: a coach finds only their teams'
  players; a portal therapist also finds other teams' players, LOCKED (no
  link, « Add to team » to the Joueurs page's name search); a clinic admin
  opens everything.
* UC-3 Archived players come last, flagged « Archived player ».
* UC-4 Teams (accessible ones, by name) and events (visible ones, by name).
* UC-5 Fewer than 2 letters: the hint, no results. No date of birth or phone
  in the answer.
* UC-6 (tours, phone + laptop) the magnifier and « / » open the sheet; typing
  shows the player; Enter / a tap opens the player page; a locked row is
  not a link.
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.app_search import sc_fold, sc_name_matches
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class Search1650Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Patients = env['sports.patient']
        cls.eloise = Patients.create({'first_name': 'Éloïse', 'last_name': 'Synthétique',
                                      'date_of_birth': '2010-03-04', 'jersey_number': '7'})
        cls.eloise.with_context(sc_phone_lenient=True).write({'phone': '+1 514-555-0190'})
        cls.eloise.team_ids = [Command.set([cls.team_a.id])]
        cls.other = Patients.create({'first_name': 'Eloi', 'last_name': 'Synthetic-Other'})
        cls.other.team_ids = [Command.set([cls.team_b.id])]
        cls.old = Patients.create({'first_name': 'Eloise', 'last_name': 'Synthetique-Archive'})
        cls.old.team_ids = [Command.set([cls.team_a.id])]
        cls.old.active = False
        cls.admin = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Search Synthetic Admin', 'login': 'search1650.admin@example.com',
            'password': 'search-1650-admin',
            'group_ids': [Command.set([
                env.ref('base.group_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_admin').id,
            ])],
        })

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _search(self, q):
        resp = self.url_open('/my/app/search?q=%s' % q)
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        return resp.text, lxml_html.fromstring('<div>%s</div>' % resp.text)

    @staticmethod
    def _players(tree):
        return {int(li.get('data-sc-search-player')): li
                for li in tree.xpath('//li[@data-sc-search-player]')}


@tagged('post_install', '-at_install')
class TestHeaderSearch1650(Search1650Common):

    def test_name_matching(self):
        self.assertEqual(sc_fold('Éloïse'), 'eloise')
        self.assertTrue(sc_name_matches(['eloi', 'syn'], 'Éloïse', 'Synthétique'))
        self.assertTrue(sc_name_matches(['synth', 'elo'], 'Éloïse', 'Synthétique'))
        self.assertFalse(sc_name_matches(['loise'], 'Éloïse', 'Synthétique'))
        self.assertTrue(sc_name_matches(['other'], 'Eloi', 'Synthetic-Other'))

    def test_coach_scope(self):
        self._login_coach()
        _text, tree = self._search('ELOI%20syn')
        players = self._players(tree)
        self.assertIn(self.eloise.id, players)
        self.assertNotIn(self.other.id, players, 'a coach never finds other teams')
        self.assertTrue(players[self.eloise.id].xpath('.//a[@href="/my/player?player_id=%s"]' % self.eloise.id))

    def test_therapist_finds_other_teams_locked(self):
        self._login_tp()
        _text, tree = self._search('eloi')
        players = self._players(tree)
        self.assertIn(self.other.id, players)
        locked = players[self.other.id]
        self.assertIn('o_sc_search_locked', locked.get('class'))
        self.assertFalse(locked.xpath('.//a[contains(@href, "/my/player?")]'))
        add = locked.xpath('.//a[contains(@class, "o_sc_search_add")]/@href')
        self.assertEqual(len(add), 1)
        self.assertTrue(add[0].startswith('/my/players?'), add)
        self.assertIn('PC Team B', locked.text_content())
        self.assertTrue(players[self.eloise.id].xpath('.//a[contains(@href, "/my/player?")]'))

    def test_admin_opens_everything(self):
        self.authenticate('search1650.admin@example.com', 'search-1650-admin')
        _text, tree = self._search('eloi')
        players = self._players(tree)
        for player in (self.eloise, self.other):
            self.assertTrue(players[player.id].xpath('.//a[@href="/my/player?player_id=%s"]' % player.id))

    def test_archived_last_and_flagged(self):
        self._login_tp()
        _text, tree = self._search('synth')
        ids = [int(li.get('data-sc-search-player')) for li in tree.xpath('//li[@data-sc-search-player]')]
        self.assertIn(self.old.id, ids)
        self.assertEqual(ids[-1], self.old.id, ids)
        row = self._players(tree)[self.old.id]
        self.assertIn('o_sc_search_archived', row.get('class'))
        self.assertIn('Archived player', row.text_content())

    def test_teams_and_events(self):
        self._login_tp()
        _text, tree = self._search('pc%20team')
        hrefs = tree.xpath('//section[@data-sc-search-group="teams"]//a/@href')
        self.assertIn('/my/team?team_id=%s' % self.team_a.id, hrefs)
        self.assertNotIn('/my/team?team_id=%s' % self.team_b.id, hrefs)
        _text, tree = self._search('pc%20ev')
        self.assertIn('/my/event/%s' % self.event.id,
                      tree.xpath('//section[@data-sc-search-group="events"]//a/@href'))

    def test_short_query_and_no_private_data(self):
        self._login_tp()
        _text, tree = self._search('e')
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_search_hint")]'))
        self.assertFalse(tree.xpath('//li[@data-sc-search-player]'))
        text, _tree = self._search('eloise')
        for private in ('2010', '514', '555-0190'):
            self.assertNotIn(private, text)
        _text, tree = self._search('zzzz')
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_empty")]'))

    def test_header_opens_the_sheet(self):
        self._login_coach()
        _text, tree = self._get('/my/home')
        opener = tree.xpath('//header//a[@data-sc-search-open]')
        self.assertEqual(len(opener), 1)
        self.assertEqual(opener[0].get('href'), '/my/players')
        self.assertTrue(tree.xpath('//dialog[@id="sc_search_sheet"]//input[@data-sc-search-input]'))


@tagged('post_install', '-at_install')
class TestHeaderSearchToursPhone1650(Search1650Common):
    browser_size = '390x844'

    def test_search_phone(self):
        self.start_tour('/my/home', 'sc_1650_search_tap', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestHeaderSearchToursLaptop1650(Search1650Common):
    browser_size = '1366x768'

    def test_search_laptop(self):
        self.start_tour('/my/home', 'sc_1650_search_keys', login='pc.tp@example.com')
