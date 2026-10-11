"""Task 1538 — the app shell renders in French (fr_CA). Synthetic fixtures.

Acceptance criterion covered here:

* UC-I1 (AC5) With the switch on and a fr_CA user, the shell's own strings
  (tabs, app bar, home sections, the « Plus » page) come out in French —
  checked by RENDER, website-aware (fr_CA added to every website's
  languages + the ``frontend_lang`` cookie when ``website`` is installed).
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellI18n1538(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.tp.write({'lang': 'fr_CA'})
        cls.coach.write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text

    def test_home_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/home')
        for term in ('Équipes', 'Joueurs', 'Clinique', 'Activités', 'Plus',
                     'Mes équipes', 'À venir', 'Blessés', 'Disponibles',
                     'Basculer le thème'):
            self.assertIn(term, text, term)
        self.assertNotIn('>My teams<', text)

    def test_teams_in_french(self):
        self._switch(True)
        self._login_coach()
        text = self._fr('/my/teams')
        for term in ('Mes équipes', 'Récemment actives', 'Alphabétique'):
            self.assertIn(term, text, term)
        self.assertNotIn('Activité récente', text)

    def test_players_sort_switch_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/players')
        # Same label as the team roster's sort (owner review 2026-10-10).
        self.assertIn('Par statut', text)
        self.assertNotIn('Plus blessés', text)

    def test_contact_practice_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/player?player_id=%s' % self.player.id)
        self.assertIn('Pratique contact', text)
        self.assertNotIn('Pratique seulement', text)

    def test_more_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/app/more')
        for term in ('Apparence', 'Sombre', 'Clair', 'Navigation',
                     'Retour + contexte', "Fil d'Ariane", 'Mon compte', 'Sécurité',
                     'Événements et calendrier', 'Bloc-notes', 'Feuilles de temps',
                     'Déconnexion'):
            self.assertIn(term, text.replace('&#39;', "'"), term)
