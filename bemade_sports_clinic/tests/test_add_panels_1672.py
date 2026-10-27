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
* AC-5 (addendum 2) From a team page the panel has NO team selector: the
  page's team is the hidden ``team_ids`` (the guard's « team required » is
  met, the server still validates it) and a create attaches that team; the
  Joueurs list keeps the selector.
* AC-6 (addendum 3) The check fragment renders in the USER's language (an
  English user gets « Possible matches: » even when the site language is
  French; a French user « Joueurs possibles : »); the namesake message is
  shown once — the reason under « Create » only points at it (« Check the
  existing player above »).
* AC-4 Browser, the injury add panel (player page): a title tap keeps it
  open; after a create success (« sc:create-success ») the panel resets
  (fields empty, closed) and reopens empty.

Real phone taps stay UNVERIFIED until /dev-review.
"""
import json

from odoo import Command
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


@tagged('post_install', '-at_install')
class TestAddPanelsAddenda1672(PlayerAdd1655Common):

    def _team_owl(self, panel):
        return [p for p in panel.xpath('.//owl-component/@props')
                if json.loads(p).get('target', '').endswith('_team_ids')]

    # -- AC-5 ----------------------------------------------------------------
    def test_team_page_has_no_team_selector(self):
        self._login_tp()
        _text, tree = self._get('/my/team?team_id=%s&tab=players' % self.team_a.id)
        panel = tree.xpath('//details[@id="sc_add_player"]')[0]
        self.assertFalse(self._team_owl(panel))
        self.assertEqual(panel.xpath('.//input[@type="hidden"][@name="team_ids"]/@value'), [str(self.team_a.id)])
        _text, tree = self._get('/my/players?add=1')
        panel = tree.xpath('//details[@id="sc_player_add"]')[0]
        self.assertEqual(len(self._team_owl(panel)), 1)

    def test_team_page_create_attaches_the_team(self):
        self._login_tp()
        resp = self._create(first_name='Implicit', last_name='Synthteam', date_of_birth='2011-05-06',
                            team_ids=str(self.team_a.id), context_team_id=str(self.team_a.id),
                            return_url='/my/team?team_id=%s&tab=players' % self.team_a.id)
        self.assertIn(resp.status_code, (200, 302, 303))
        created = self.env['sports.patient'].search([('last_name', '=', 'Synthteam')])
        self.assertEqual(created.team_ids, self.team_a)

    # -- AC-6 ----------------------------------------------------------------
    def _french_site(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
                website.default_lang_id = fr_lang
        self.opener.cookies.set('frontend_lang', 'fr_CA')

    def test_check_fragment_in_the_users_language(self):
        self._french_site()
        self.tp.write({'lang': 'en_US'})
        self._login_tp()
        resp, tree = self._check(first='elo', last='synthe')
        self.assertIn('Possible matches:', resp.text)
        self.assertNotIn('Joueurs possibles', resp.text)
        self.tp.write({'lang': 'fr_CA'})
        resp, tree = self._check(first='elo', last='synthe')
        self.assertIn('Joueurs possibles', resp.text)

    def test_namesake_message_once(self):
        self._login_tp()
        _text, tree = self._get('/my/players?add=1')
        reasons = tree.xpath('//details[@id="sc_player_add"]//*[@data-sc-player-add-reasons]')[0]
        self.assertEqual(reasons.get('data-twin'), 'Check the existing player above')
        resp, tree = self._check(first='Élodie', last='Synthé-Côté')
        self.assertEqual(resp.text.count('A player with this identity already exists'), 1)


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
