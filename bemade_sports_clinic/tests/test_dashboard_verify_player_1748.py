"""Task 1748 — dashboard « Blessures à vérifier »: each injury card names its
player and links to the player's file. Synthetic fixtures only (this
repository is public).

Acceptance criteria:

* UC-1 On the dashboard, each card of « Injuries to verify » carries a header
  line INSIDE the card (its summary, so it leaves with the card): the
  player's list name (« #12 Last, First ») and their teams (the viewer's
  teams only, « · »-separated).
* UC-2 The name is a link to the player page, Injuries tab, with THAT injury
  unfolded (``&tab=injuries&injury=<id>#injury-<id>``, the team context
  kept); opening it renders the card open.
* UC-3 The player page (where the player is obvious) shows no such header.
* UC-4 « Vérifier » / « Résoudre » stay on the card; after « Vérifier » the
  card (header included) leaves the list fragment (#1740 kept).
* UC-5 In a browser, phone 390 px and laptop 1440 px: the header shows the
  name + team, the name opens the player on Blessures with the injury
  unfolded; back on the dashboard, « Vérifier » still drops the card
  (static/tests/tours/sc_verify_player_1748_tours.js).
"""
from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin

LIST_KEY = 'sc.dashboard:todo:dash-todo-verify:list'


class _Player1748:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Injury = cls.env['sports.patient.injury']
        # Yellow: Team C only; Shared: Team A + Team C (two teams).
        cls.inj_yellow = Injury.create({'patient_id': cls.yellow.id, 'diagnosis': 'Synthetic sprain 1748'})
        cls.inj_shared = Injury.create({'patient_id': cls.shared.id, 'diagnosis': 'Synthetic strain 1748'})
        (cls.inj_yellow | cls.inj_shared).with_context(mail_notrack=True).write({'stage': 'unverified'})


@tagged('post_install', '-at_install')
class TestVerifyCardPlayer1748(_Player1748, FragmentsMixin, Dashboard1624Common):

    def _card(self, tree, injury):
        found = tree.xpath('//details[@data-sc-edit-card="injury"][@data-sc-injury-id="%s"]' % injury.id)
        self.assertEqual(len(found), 1, injury.diagnosis)
        return found[0]

    def _verify_line(self, tree):
        todo = self._section(tree, 'todo')
        return todo.xpath('.//details[@data-sc-todo="verify"]')[0]

    # -- UC-1 ---------------------------------------------------------------
    def test_dashboard_card_names_the_player(self):
        self._login_tp()
        _text, tree = self._get('/my/home')
        line = self._verify_line(tree)
        for injury, teams in ((self.inj_yellow, [self.team_c]),
                              (self.inj_shared, [self.team_a, self.team_c])):
            card = self._card(line, injury)
            heads = card.xpath('./summary/*[@data-sc-injury-player]')
            self.assertEqual(len(heads), 1, 'the header sits in the card summary')
            link = heads[0].xpath('.//a[@data-sc-injury-player-link]')[0]
            self.assertEqual(link.text_content().strip(), injury.patient_id._portal_list_name())
            self.assertEqual(link.get('data-sc-injury-player-link'), str(injury.patient_id.id))
            team_text = self._text(heads[0].xpath('.//*[contains(@class, "o_sc_injury_player_teams")]')[0])
            for team in teams:
                self.assertIn(team.name, team_text)
            self.assertIn('o_sc_injury_head_with_player', card.xpath('./summary')[0].get('class'))
            # UC-4: the quick « Verify » stays on the card.
            self.assertTrue(card.xpath('.//button[@data-sc-injury-quick="verify"]'))

    def test_teams_outside_my_universe_are_not_named(self):
        """Team B is staffed by nobody of ours: never named in the header."""
        self.shared.write({'team_ids': [(4, self.team_b.id)]})
        self._login_tp()
        _text, tree = self._get('/my/home')
        head = self._card(self._verify_line(tree), self.inj_shared).xpath(
            './summary/*[@data-sc-injury-player]')[0]
        self.assertNotIn(self.team_b.name, self._text(head))

    # -- UC-2 ---------------------------------------------------------------
    def test_name_opens_the_player_on_that_injury(self):
        self._login_tp()
        _text, tree = self._get('/my/home')
        href = self._card(self._verify_line(tree), self.inj_yellow).xpath(
            './/a[@data-sc-injury-player-link]/@href')[0]
        self.assertTrue(href.startswith('/my/player?player_id=%s' % self.yellow.id), href)
        self.assertIn('team_id=%s' % self.team_c.id, href)
        self.assertIn('tab=injuries', href)
        self.assertTrue(href.endswith('&injury=%s#injury-%s' % (self.inj_yellow.id, self.inj_yellow.id)), href)
        _text, page = self._get(href.split('#')[0])
        card = page.xpath('//details[@id="injury-%s"]' % self.inj_yellow.id)
        self.assertEqual(len(card), 1)
        self.assertEqual(card[0].get('open'), 'open', 'the linked injury is unfolded')
        other = page.xpath('//details[@data-sc-edit-card="injury"][not(@id="injury-%s")]' % self.inj_yellow.id)
        self.assertFalse([c for c in other if c.get('open')], 'only that injury is unfolded')

    # -- UC-3 ---------------------------------------------------------------
    def test_player_page_has_no_player_header(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=injuries' % self.shared.id)
        self.assertTrue(tree.xpath('//details[@id="injury-%s"]' % self.inj_shared.id))
        self.assertFalse(tree.xpath('//*[@data-sc-injury-player]'))
        self.assertFalse(tree.xpath('//summary[contains(@class, "o_sc_injury_head_with_player")]'))

    # -- UC-4 ---------------------------------------------------------------
    def test_verify_still_drops_the_card_with_its_header(self):
        self._login_tp()
        resp = self.url_open('/my/injury/%s/verify' % self.inj_yellow.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertRefreshes(resp.json(), LIST_KEY)
        answer = self._fragments('/my/home', [LIST_KEY])
        line = lxml_html.fragment_fromstring(answer['fragments'][LIST_KEY])
        ids = line.xpath('.//*[@data-sc-injury-player-link]/@data-sc-injury-player-link')
        self.assertEqual(ids, [str(self.shared.id)])


class _Tour1748(_Player1748, Dashboard1624Common):

    def _run(self):
        self.start_tour('/my/home', 'sc_1748_verify_card_player', login='pc.tp@example.com')
        self.assertEqual(self.inj_yellow.stage, 'active', 'the tour verified the yellow injury')
        self.assertEqual(self.inj_shared.stage, 'unverified')


@tagged('post_install', '-at_install')
class TestVerifyCardPlayerTourPhone1748(_Tour1748):
    browser_size = '390x844'

    def test_verify_card_player_tour_phone(self):
        self._run()


@tagged('post_install', '-at_install')
class TestVerifyCardPlayerTourLaptop1748(_Tour1748):
    browser_size = '1440x900'

    def test_verify_card_player_tour_laptop(self):
        self._run()
