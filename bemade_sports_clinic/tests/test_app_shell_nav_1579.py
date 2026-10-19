"""Task 1579 — the portal app shell's breadcrumb / back-navigation engine.
Synthetic fixtures only.

Acceptance criteria covered here (the browser behaviour — back = where you
came from, deep-link fallback, width-based display — is in
test_app_shell_tours_1579.py):

* UC-N1 Parent registry: every page template of the shell (every template
  that calls ``sc_app_layout``) and every shell page a controller renders has
  a registry entry (``models/sc_app_nav.py``); every page that is not
  declared top level has a parent. A new page without one fails here.
* UC-N2 Labels per record type: a team crumb reads the team name, a player
  « #12 Last, First », an injury its diagnosis, a clinic its name, the digest
  list « Digest history ».
* UC-N3 Return URL validation (ONE validator): an external host,
  ``javascript:``, ``//host``, a backslash / control character, a non-shell
  path and a record the user cannot read are ignored — the declared parent
  wins; a readable in-app page is honoured (its query kept).
* UC-N4 Every sub-page renders BOTH the back chevron (href = the resolved
  parent) with the context line AND the crumb trail (``<nav aria-label>`` +
  ``<ol>``, the current page last with ``aria-current="page"``); the screen
  width decides which one shows. A top-level page renders the logo and
  neither of them.
* UC-N5 Several parents: a player opened from a team goes back to the team's
  players tab (Teams › Team), from a clinic to the clinic (Clinic › clinic
  name), otherwise to the players list; with ``return_url=/my/home`` to the
  home. The injury pages keep the player's context.
* UC-N6 Digest chain: the team page's « History » link goes straight to the
  digest list (no popup); list → team page; snapshot → list (Teams › Team ›
  Digest history).
* UC-N7 No navigation setting: ``res.users.sc_nav_mode`` is gone, « Plus »
  has no « Navigation » section, ``/my/app/pref`` refuses the key and the
  shell root carries no ``data-sc-nav``.
* UC-N8 Save-and-redirect hygiene: creating an injury from the shell's full
  « new injury » page redirects (GET) to the player's Injuries tab with the
  new injury open — never a POST result page.
* UC-N9 French: the crumb trail and the static labels render in fr_CA.
"""
import os
import re
from datetime import timedelta

from odoo import Command, fields
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models import sc_app_nav
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common

HOME = '/my/home'


class Nav1579Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.player.jersey_number = '12'
        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'SC 1579 Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': now, 'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.player.id})
        today = fields.Date.today()
        cls.digest = env['sports.team.digest'].create({
            'team_id': cls.team_a.id, 'snapshot_date': today,
            'captured_at': fields.Datetime.now(), 'item_data': {},
        })
        cls.team_url = '/my/team?team_id=%s' % cls.team_a.id
        cls.players_tab = cls.team_url + '&tab=players'
        cls.player_name = '#12 One, Pat'

    def setUp(self):
        super().setUp()
        self._switch(True)
        self._login_tp()

    def _nav(self, url):
        """(back hrefs, [(crumb href, label)], current crumb, context line)."""
        _text, tree = self._get(url)
        back = tree.xpath('//a[contains(concat(" ", @class, " "), " o_sc_back ")]/@href')
        trail = tree.xpath('//nav[contains(concat(" ", @class, " "), " o_sc_crumbs ")]')
        crumbs, current = [], None
        if trail:
            crumbs = [(a.get('href'), a.text_content().strip())
                      for a in trail[0].xpath('./ol/li/a')]
            last = trail[0].xpath('./ol/li[@aria-current="page"]')
            current = last[0].text_content().strip() if last else None
        context = tree.xpath('//*[contains(@class, "o_sc_appbar_context")]')
        return back, crumbs, current, (context[0].text_content().strip() if context else None)


@tagged('post_install', '-at_install')
class TestAppShellNav1579(Nav1579Common):

    # -- UC-N1 -----------------------------------------------------------
    def test_every_shell_page_has_a_registry_entry(self):
        views = self.env['ir.ui.view'].search([
            ('key', '=like', 'bemade_sports_clinic.sc_app_%'), ('type', '=', 'qweb')])
        pages = {
            view.key.split('.', 1)[1] for view in views
            if view.key != 'bemade_sports_clinic.sc_app_layout'
            and 't-call="bemade_sports_clinic.sc_app_layout"' in (view.arch_db or '')
        }
        self.assertIn('sc_app_player', pages)
        self.assertFalse(pages - set(sc_app_nav.PAGES), 'pages without a registry entry')
        # And every shell page a controller renders.
        root = os.path.join(get_module_path('bemade_sports_clinic'), 'controllers')
        rendered = set()
        for name in os.listdir(root):
            if name.endswith('.py'):
                with open(os.path.join(root, name), encoding='utf-8') as handle:
                    rendered |= set(re.findall(r"'bemade_sports_clinic\.(sc_app_\w+)'", handle.read()))
        rendered -= {'sc_app_offline'}  # standalone page, no app layout
        self.assertIn('sc_app_team', rendered)
        self.assertFalse(rendered - set(sc_app_nav.PAGES), 'rendered pages without an entry')

    def test_every_sub_page_declares_a_parent(self):
        self.assertTrue(sc_app_nav.TOP_LEVEL <= set(sc_app_nav.PAGES))
        orphans = [key for key, page in sc_app_nav.PAGES.items()
                   if key not in sc_app_nav.TOP_LEVEL and not page.has_parent]
        self.assertFalse(orphans, 'shell pages without a parent')

    # -- UC-N2 / UC-N4 ---------------------------------------------------
    def test_top_level_page_has_logo_no_back_no_trail(self):
        _text, tree = self._get('/my/teams')
        self.assertTrue(tree.xpath('//a[contains(@class, "o_sc_logo")]'))
        back, crumbs, current, _context = self._nav('/my/teams')
        self.assertEqual((back, crumbs, current), ([], [], None))

    def test_sub_page_renders_back_and_accessible_trail(self):
        _text, tree = self._get(self.team_url)
        nav = tree.xpath('//nav[contains(@class, "o_sc_crumbs")]')
        self.assertEqual(len(nav), 1)
        self.assertTrue(nav[0].get('aria-label'))
        self.assertTrue(nav[0].xpath('./ol/li'))
        back, crumbs, current, context = self._nav(self.team_url)
        self.assertEqual(back, ['/my/teams'])
        self.assertEqual(crumbs, [('/my/teams', 'Teams')])
        self.assertEqual(current, 'PC Team A')
        self.assertEqual(context, 'PC Org')

    def test_player_from_team(self):
        back, crumbs, current, context = self._nav(
            '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertEqual(back, [self.players_tab])
        self.assertEqual(crumbs, [('/my/teams', 'Teams'), (self.players_tab, 'PC Team A')])
        self.assertEqual(current, self.player_name)
        self.assertTrue(context.startswith('PC Team A'), context)

    def test_player_from_clinic(self):
        back, crumbs, _current, _context = self._nav(
            '/my/player?player_id=%s&clinic_id=%s' % (self.player.id, self.clinic.id))
        clinic_url = '/my/clinic/%s' % self.clinic.id
        self.assertEqual(back, [clinic_url])
        self.assertEqual(crumbs, [('/my/clinics', 'Clinic'), (clinic_url, 'SC 1579 Clinic')])

    def test_player_from_players_list(self):
        back, crumbs, _current, _context = self._nav('/my/player?player_id=%s' % self.player.id)
        self.assertEqual(back, ['/my/players'])
        self.assertEqual(crumbs, [('/my/players', 'Players')])

    def test_player_from_dashboard_return_url(self):
        back, crumbs, _current, _context = self._nav(
            '/my/player?player_id=%s&return_url=%%2Fmy%%2Fhome' % self.player.id)
        self.assertEqual(back, [HOME])
        self.assertEqual(crumbs, [(HOME, 'Dashboard')])

    def test_injury_pages_keep_the_player_context(self):
        # Task 1616: the injury page and its documents page are the injury's
        # open card on the player page — same team context, same crumbs.
        player_url = '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)
        for old in ('/my/injury/edit?injury_id=%s&team_id=%s', '/my/injury/documents?injury_id=%s&team_id=%s'):
            back, crumbs, current, context = self._nav(old % (self.injury.id, self.team_a.id))
            self.assertEqual(back, [self.players_tab], old)
            self.assertEqual(crumbs, [('/my/teams', 'Teams'), (self.players_tab, 'PC Team A')], old)
            self.assertEqual(current, self.player_name, old)
            resp = self.url_open(old % (self.injury.id, self.team_a.id), allow_redirects=False)
            self.assertIn('%s&tab=injuries&injury=%s#injury-%s' % (player_url, self.injury.id, self.injury.id),
                          resp.headers.get('Location', ''))

    def test_clinic_and_event_pages(self):
        back, crumbs, current, _context = self._nav('/my/clinic/%s' % self.clinic.id)
        self.assertEqual(back, ['/my/clinics'])
        self.assertEqual(current, 'SC 1579 Clinic')
        back, crumbs, _current, _context = self._nav('/my/event/%s' % self.event.id)
        self.assertEqual(back, ['/my/events'])
        self.assertEqual(crumbs, [('/my/app/more', 'More'), ('/my/events', 'Events and calendar')])

    # -- UC-N3 -----------------------------------------------------------
    def test_untrusted_return_url_is_ignored(self):
        base = '/my/player?player_id=%s&return_url=' % self.player.id
        for bad in ('https%3A%2F%2Fevil.example%2Fmy%2Fhome', '%2F%2Fevil.example',
                    'javascript%3Aalert(1)', '%2F%5Cevil.example', '%2Fmy%2Fhome%09x',
                    '%2Fweb%2Flogin', '%2Fmy%2Faccount',
                    '%2Fmy%2Fteam%3Fteam_id%3D' + str(self.team_unstaffed.id)):
            back, _crumbs, _current, _context = self._nav(base + bad)
            self.assertEqual(back, ['/my/players'], bad)

    def test_match_url_validator(self):
        env = self.env(user=self.coach)
        for bad in ('https://evil.example/my/home', '//evil.example/my/home',
                    'javascript:alert(1)', '/\\evil.example', '/my/home\tx',
                    '/web/login', '/my/account', 'my/home', '',
                    '/my/player?player_id=%s' % self.player_c.id,
                    '/my/team?team_id=%s' % self.team_unstaffed.id,
                    '/my/team?team_id=999999999', '/my/team?team_id=abc'):
            self.assertIsNone(sc_app_nav.match_url(env, bad), bad)
        key, values = sc_app_nav.match_url(env, '/my/team?team_id=%s&tab=players' % self.team_a.id)
        self.assertEqual((key, values['team']), ('sc_app_team', self.team_a))
        self.assertEqual(sc_app_nav.match_url(env, HOME)[0], 'sc_app_home')

    def test_one_safe_return_url_validator(self):
        safe = sc_app_nav.safe_return_url
        self.assertEqual(safe('/my/teams', 'x'), '/my/teams')
        for bad in (None, 42, 'https://evil', '//evil', '/\\evil', '/a\nb', 'javascript:x'):
            self.assertEqual(safe(bad, 'fb'), 'fb', bad)
        self.assertEqual(safe('/my/teams', None, prefixes=('/my/events', HOME)), None)
        self.assertEqual(safe('/my/events?x=1', None, prefixes=('/my/events', HOME)),
                         '/my/events?x=1')

    # -- UC-N6 -----------------------------------------------------------
    def test_digest_chain(self):
        _text, tree = self._get(self.team_url)
        history_url = '/my/team/%s/digest-history' % self.team_a.id
        links = tree.xpath('//*[@data-sc-section="team.recent_changes"]'
                           '//a[@data-sc-action="team.digest_history"]/@href')
        self.assertEqual(links, [history_url])
        self.assertFalse(tree.xpath('//dialog[@id="sc_digest_history_sheet"]'))
        back, crumbs, current, _context = self._nav(history_url)
        self.assertEqual(back, [self.team_url])
        self.assertEqual(crumbs, [('/my/teams', 'Teams'), (self.team_url, 'PC Team A')])
        self.assertEqual(current, 'Digest history')
        back, crumbs, _current, context = self._nav(
            '/my/team/%s/digest/%s' % (self.team_a.id, self.digest.id))
        self.assertEqual(back, [history_url])
        self.assertEqual(crumbs, [('/my/teams', 'Teams'), (self.team_url, 'PC Team A'),
                                  (history_url, 'Digest history')])
        self.assertEqual(context, 'PC Team A')

    # -- UC-N7 -----------------------------------------------------------
    def test_no_navigation_setting(self):
        self.assertNotIn('sc_nav_mode', self.env['res.users']._fields)
        _text, tree = self._get('/my/app/more')
        self.assertFalse(tree.xpath('//*[@id="sc_navigation"]'))
        self.assertFalse(tree.xpath('//*[@name="sc_nav_mode"]'))
        self.assertIsNone(self._shell(tree).get('data-sc-nav'))
        resp = self.url_open('/my/app/pref', data={
            'csrf_token': self._csrf(), 'sc_nav_mode': 'crumbs'},
            headers={'Accept': 'application/json'}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400)

    # -- UC-N8 -----------------------------------------------------------
    def test_injury_create_redirects_to_the_player(self):
        self._login_coach()
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'diagnosis': 'Synthetic 1579 report', 'injury_date': '2026-03-03',
            'team_id': self.team_a.id,
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        injury = self.env['sports.patient.injury'].search(
            [('diagnosis', '=', 'Synthetic 1579 report')])
        self.assertEqual(len(injury), 1)
        location = resp.headers['Location']
        self.assertIn('/my/player?player_id=%s' % self.player.id, location)
        self.assertIn('tab=injuries', location)
        self.assertIn('created=%s' % injury.id, location)


@tagged('post_install', '-at_install')
class TestAppShellNavFr1579(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_trail_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id))
        self.assertIn('>Équipes</a>', text)
        self.assertIn('aria-label="Fil d\'Ariane"', text.replace('&#39;', "'"))
        text = self._fr('/my/player?player_id=%s&return_url=%%2Fmy%%2Fhome' % self.player.id)
        self.assertIn('>Tableau de bord</a>', text)  # #1623: breadcrumb root renamed
        text = self._fr('/my/team/%s/digest-history' % self.team_a.id)
        self.assertIn('Historique des sommaires', text)
