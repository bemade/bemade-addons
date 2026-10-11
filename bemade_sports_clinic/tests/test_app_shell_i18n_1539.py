"""Task 1539 — the P2 shell pages render in French (fr_CA). Synthetic
fixtures only.

Acceptance criterion covered here (AC6, fr_CA complete for new strings):

* UC-F1 Server render, website-aware (fr_CA added to every website's
  languages + the ``frontend_lang`` cookie when ``website`` is installed):
  players list, player page, player form, new injury, injury edit, notes,
  documents and activities come out in French.
* UC-F2 The OWL component's new strings (``_t``) are served to the
  frontend in French.
"""
import json

from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestAppShellI18n1539(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None

    def _fr_text(self, url):
        """The page text + the (JSON-escaped) labels of its OWL fields."""
        text = self._fr(url).replace('&#39;', "'")
        tree = lxml_html.fromstring(text)
        for node in tree.xpath('//owl-component[@props]'):
            props = json.loads(node.get('props'))
            text += '\n' + ' | '.join(
                [str(props.get(key) or '') for key in ('label', 'hint', 'undoMessage')]
                + [str(opt[1]) for opt in props.get('options') or []])
        return text

    def test_player_pages_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr_text('/my/players')
        for term in ('Filtres', 'Effacer les filtres', 'Créer un joueur', 'Rechercher'):
            self.assertIn(term, text, term)
        text = self._fr_text('/my/player?player_id=%s' % self.player.id)
        for term in ('Aperçu', 'Blessures', 'Infos', 'Ajouter une blessure',
                     'Statut de jeu', 'Prochains événements', 'Blessures actives',
                     "Appartenance à l'équipe", 'Ajouter une note de traitement',
                     'Ajouter une activité', 'Match + pratique', 'Aucun jeu'):
            self.assertIn(term, text, term)
        # The retired edit page's fields, inline on the Info tab (2026-10-10).
        text = self._fr_text('/my/player?player_id=%s&tab=info' % self.player.id)
        for term in ('Informations médicales', 'Code postal', 'Terminé'):
            self.assertIn(term, text, term)

    def test_injury_pages_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr_text('/my/patient/injury/new?patient_id=%s' % self.player.id)
        for term in ("Gardée sur cet appareil jusqu'à sa création", 'Créer une blessure',
                     'Cochez S/O si la date exacte est inconnue'):
            self.assertIn(term, text, term)
        text = self._fr_text('/my/injury/edit?injury_id=%s' % self.injury.id)
        for term in ('Statut de la blessure', 'Visibilité', 'Entraîneurs', 'Masquée',
                     'Historique des notes', 'Oui, supprimer la blessure', 'Supprimer'):
            self.assertIn(term, text, term)
        text = self._fr_text('/my/injury/documents?injury_id=%s' % self.injury.id)
        for term in ('Téléverser un document', 'Taille max 10 Mo', 'Téléverser'):
            self.assertIn(term, text, term)

    def test_activities_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr_text('/my/activities')
        for term in ('Toutes (', 'En retard (', "Aujourd'hui (", 'Planifiées (',
                     "Terminer l'activité", 'Reprogrammer'):
            self.assertIn(term, text, term)

    def test_p2_owl_strings_served_in_french(self):
        resp = self.url_open('/web/webclient/translations?lang=fr_CA&mods=bemade_sports_clinic')
        messages = {
            m['id']: m['string']
            for m in resp.json()['modules']['bemade_sports_clinic']['messages']}
        for source, french in (('Undo', 'Annuler'), ('Change saved', 'Modification enregistrée'),
                               ('N/A', 'S/O'), ('Clear', 'Effacer')):
            self.assertEqual(messages.get(source), french, source)
