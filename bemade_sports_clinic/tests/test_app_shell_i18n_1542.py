"""Task 1542 — the P1b shell pages render in French (fr_CA). Synthetic
fixtures only.

Acceptance criterion covered here (AC6, fr_CA complete for new strings):

* UC-F1 Server render, website-aware (fr_CA added to every website's
  languages + the ``frontend_lang`` cookie when ``website`` is installed):
  the team page, « Installer l'application » and the offline page come out in
  French.
* UC-F2 The OWL component's strings (template + ``_t``) are served to the
  frontend in French and render in French in a browser (« Brouillon gardé
  sur cet appareil », « Brouillon restauré », « Jeter le brouillon »).
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestAppShellI18n1542(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.url = '/my/team?team_id=%s' % cls.team_a.id

    def test_team_page_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr(self.url).replace('&#39;', "'")
        # The frontend JS (OWL _t) picks its language from <html lang>.
        html_tag = text[text.index('<html'):text.index('>', text.index('<html')) + 1]
        self.assertIn('lang="fr-CA"', html_tag)
        for term in ('Aperçu', 'Joueurs', 'Activités', 'Ajouter un joueur',
                     'Changements récents', 'Blessés', 'En reprise', 'Disponibles',
                     "Publier une annonce d'équipe", 'Publier', 'Historique des sommaires',
                     'Événements à venir', 'Par statut', 'Par numéro', 'Chargement…'):
            self.assertIn(term, text, term)
        self._login_coach()
        text = self._fr(self.url).replace('&#39;', "'")
        for term in ('Demander un ajout', "Demander l'ajout d'un joueur", 'Envoyer la demande'):
            self.assertIn(term, text, term)

    def test_install_and_offline_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/app/install').replace('&#39;', "'")
        for term in ("Installer l'application", 'iPhone et iPad (Safari)',
                     'Touchez le bouton Partager', "L'application est installée"):
            self.assertIn(term, text, term)
        text = self._fr('/my/app/more').replace('&#39;', "'")
        self.assertIn("Ajouter Le Fit Crew à l'écran d'accueil", text)
        text = self._fr('/my/app/offline').replace('&#39;', "'")
        for term in ('Vous êtes hors ligne', 'Réessayer'):
            self.assertIn(term, text, term)
        # A real doctype, not an escaped one shown as text on the page.
        self.assertTrue(text.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('&lt;!DOCTYPE', text)

    def test_owl_strings_served_in_french(self):
        resp = self.url_open('/web/webclient/translations?lang=fr_CA&mods=bemade_sports_clinic')
        messages = {
            m['id']: m['string']
            for m in resp.json()['modules']['bemade_sports_clinic']['messages']}
        for source, french in (('Draft restored', 'Brouillon restauré'),
                               ('Saving…', 'Enregistrement…'),
                               ('Offline — pending', 'Hors ligne — en attente'),
                               ('Keep mine', 'Garder le mien'),
                               ('Take theirs', 'Prendre le leur')):
            self.assertEqual(messages.get(source), french, source)

    def test_owl_component_renders_in_french(self):
        self._switch(True)
        self.start_tour(self.url, 'sc_1542_fr_draft', login='pc.tp@example.com')
