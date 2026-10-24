"""Task 1672 — « + Ajouter » panels: the title bar never toggles, the panel
resets after a successful create; the add-player suggestions show each
player's date of birth. Synthetic fixtures only.

Acceptance criteria:

* AC-1 /my/app/player-check: each suggested player shows its OWN date of
  birth (``data-sc-check-dob``), in-team and out-of-team alike.
* AC-2 S2 invariant kept: for an out-of-scope player the whole answer is the
  same whatever date is typed (the row's own date shown, never filtered,
  ordered or flagged by the typed one).
* AC-3 Browser (phone 390 px + laptop 1366 px), team page Joueurs tab:
  « + Ajouter » opens the panel; a tap on its title keeps it open; name +
  date of birth + emergency contact → « Créer » → the player page; back on
  the team page, reopening the panel shows an EMPTY form with the team
  pre-filled again and no existence-check rows; the « + Ajouter » toggle
  still closes and reopens it.
* AC-4 Browser, the injury add panel (player page): a title tap keeps it
  open; after a create success (« sc:create-success ») the panel resets
  (fields empty, closed) and reopens empty.

Real phone taps stay UNVERIFIED until /dev-review.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_player_add_inline_1655 import PlayerAdd1655Common


@tagged('post_install', '-at_install')
class TestAddPanelsCheckDob1672(PlayerAdd1655Common):

    def _dob(self, tree, player):
        return [' '.join(n.text_content().split())
                for n in tree.xpath('//li[@data-sc-check-player="%s"]//*[@data-sc-check-dob]' % player.id)]

    def test_suggestions_show_each_players_dob(self):
        self._login_tp()
        _resp, tree = self._check(first='Pat', last='One')
        self.assertEqual(self._dob(tree, self.player), ['Born on 04/05/2009'])
        _resp, tree = self._check(first='elodie', last='synthe')
        self.assertEqual(self._dob(tree, self.elodie), ['Born on 02/03/2010'])
        # No date of birth: no line.
        self.assertFalse(self._dob(tree, self.archived))

    def test_out_of_scope_answer_independent_of_typed_dob(self):
        self._login_tp()
        answers = []
        for dob in ('2010-02-03', '2001-01-01', ''):
            resp, tree = self._check(first='elo', last='synthe', dob=dob)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(self._dob(tree, self.elodie), ['Born on 02/03/2010'], dob)
            answers.append(resp.text)
        self.assertEqual(answers[0], answers[1])
        self.assertEqual(answers[0], answers[2])


class _Tours1672:

    def test_team_add_player_panel(self):
        url = '/my/team?team_id=%s&tab=players' % self.team_a.id
        self.start_tour(url, 'sc_1672_team_add_player', login='pc.tp@example.com')
        created = self.env['sports.patient'].search([('first_name', '=', 'Tourone'), ('last_name', '=', 'Synthfirst')])
        self.assertEqual(len(created), 1)
        self.assertIn(self.team_a, created.team_ids)

    def test_injury_add_panel(self):
        self.start_tour('/my/player?player_id=%s&tab=injuries' % self.player.id, 'sc_1672_injury_add_panel',
                        login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestAddPanelsPhone1672(_Tours1672, PlayerAdd1655Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestAddPanelsLaptop1672(_Tours1672, PlayerAdd1655Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
