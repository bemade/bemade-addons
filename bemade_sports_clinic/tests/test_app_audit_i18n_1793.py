"""Task 1793 (epic #1535, P4b) — the French pass: the app strings the
fr_CA export still showed untranslated are French. Synthetic fixtures.

Acceptance criteria covered here:

* UC-F1 The followed-player star of the players list (its title and its
  screen-reader text) renders in French for a fr_CA user.
* UC-F2 The Python strings an app user meets (the anonymized placeholder
  names, the digest synopsis line) come out in French in a fr_CA context.
* UC-F3 The field labels the app shows are French (« Événements
  assignés »).
* UC-F4 The main screens render French as therapist and as coach (server
  render, website-aware: fr_CA added to every website's languages and the
  ``frontend_lang`` cookie): no English label of the audited screens left.
"""
import re

from lxml import html as lxml_html

from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestAppAuditI18n1793(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The home's widgets are the kit dashboard's.
        cls.env['ir.module.module']._load_module_terms(['bemade_portal_kit_dashboard'], ['fr_CA'], overwrite=True)

    def _fr_env(self):
        return self.env(context=dict(self.env.context, lang='fr_CA'))

    # -- UC-F1 -----------------------------------------------------------
    def test_followed_star_in_french(self):
        html = str(self._fr_env()['ir.qweb']._render(
            'bemade_sports_clinic.sc_players_row_followed', {'row': {'followed': True}}))
        self.assertEqual(html.count('Vous suivez ce joueur'), 2, html)
        self.assertNotIn('You follow', html)

    # -- UC-F2 -----------------------------------------------------------
    def test_python_strings_in_french(self):
        env = self._fr_env()
        self.assertEqual(env._("Player %s") % 7, 'Joueur 7')
        self.assertEqual(env._("Anonymized"), 'Anonymisé')
        self.assertEqual(env._("Anonymized Contact %s") % 7, 'Contact anonymisé 7')
        self.assertEqual(
            env._("%(players)s player(s) with changes · %(new)s new injury/injuries · %(notes)s note update(s)",
                  players=2, new=1, notes=3),
            '2 joueur(s) avec changements · 1 nouvelle(s) blessure(s) · 3 mise(s) à jour de note')

    # -- UC-F3 -----------------------------------------------------------
    def test_labels_in_french(self):
        env = self._fr_env()
        self.assertEqual(env['res.users']._fields['sc_assigned_event_ids']._description_string(env),
                         'Événements assignés')

    # -- UC-F4 -----------------------------------------------------------
    def _english_labels(self):
        """The short English UI labels the clinic and the kit translate to
        something else in French (msgid != msgstr): any of them showing as a
        whole text node of a French page is an untranslated label."""
        labels, same = set(), set()
        for module in ('bemade_sports_clinic', 'bemade_portal_kit', 'bemade_portal_kit_dashboard'):
            try:
                with file_open('%s/i18n/fr.po' % module) as handle:
                    text = handle.read()
            except FileNotFoundError:
                continue
            for msgid, msgstr in re.findall(r'^msgid "(.+)"\nmsgstr "(.+)"$', text, re.M):
                if msgid == msgstr:
                    # French as is in one module (« Active », a feminine
                    # injury stage), whatever another module makes of it.
                    same.add(msgid)
                elif len(msgid) <= 40 and '<' not in msgid and '%' not in msgid \
                        and re.search(r'[A-Za-z]{3}', msgid):
                    labels.add(msgid.replace('\\"', '"'))
        # The fixtures' own data (the superuser's name).
        return labels - same - {self.env.ref('base.user_admin').name}

    def _leaks(self, url, labels):
        text = self._fr(url)
        tree = lxml_html.fromstring(text)
        shell = self._shell(tree)
        self.assertIsNotNone(shell, url)
        nodes = {' '.join(t.split()) for t in shell.xpath('.//text()[not(ancestor::script)][not(ancestor::template)]')}
        return sorted(nodes & labels)

    def test_main_screens_render_french(self):
        self._switch(True)
        labels = self._english_labels()
        self.assertGreater(len(labels), 200)
        team = '/my/team?team_id=%s' % self.team_a.id
        player = '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)
        screens = {
            self._login_tp: ['/my/home', '/my/teams', team, team + '&tab=activities', player,
                             player + '&tab=injuries', '/my/events', '/my/activities', '/my/clinics',
                             '/my/notepad', '/my/app/more', '/my/app/settings'],
            self._login_coach: ['/my/home', '/my/teams', team, player, player + '&tab=injuries',
                                '/my/events', '/my/activities', '/my/app/more'],
        }
        leaks = {}
        for login, urls in screens.items():
            login()
            for url in urls:
                found = self._leaks(url, labels)
                if found:
                    leaks['%s %s' % (login.__name__, url)] = found
        self.assertFalse(leaks, 'English labels on French screens: %s' % leaks)
