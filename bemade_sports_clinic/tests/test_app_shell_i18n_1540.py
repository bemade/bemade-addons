"""Task 1540 — the P3 shell pages render in French (fr_CA). Synthetic
fixtures only.

Acceptance criterion covered here (AC6, fr_CA complete for new strings):

* UC-F1 Server render, website-aware (fr_CA added to every website's
  languages + the ``frontend_lang`` cookie when ``website`` is installed):
  clinic list and page (incl. the live list's JSON counts line), events,
  event form, timesheets, notepad come out in French.
* UC-F2 The new OWL strings (``_t`` and template text of the live list and
  the calendar) are served to the frontend in French.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestAppShellI18n1540(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = max(day_start, min(now, day_start + timedelta(hours=21)))
        cls.clinic = cls.env['sports.event'].create({
            'name': 'FR 1540 Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2), 'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        cls.env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.player.id})

    def test_clinic_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/clinics')
        for term in ("Aujourd'hui", 'À venir', 'Qui me sont assignées', 'Filtres', '1 sur la liste'):
            self.assertIn(term, text.replace('&#39;', "'"), term)
        text = self._fr('/my/clinic/%s?patient=%s' % (self.clinic.id, self.player.id)).replace('&#39;', "'")
        for term in ("Liste d'attente", 'Dossier', 'Ajouter un patient', 'Dossier complet',
                     'Nouvelle blessure', 'Notes de traitement', "Résoudre l'inscription",
                     "Borne d'inscription"):
            self.assertIn(term, text, term)
        data = self.url_open('/my/clinic/%s/worklist/data' % self.clinic.id).json()
        self.assertIn('Présences', data['countsLine'])
        self.assertIn('attendu', data['countsLine'])

    def test_events_and_tools_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/events?no_default_dates=1').replace('&#39;', "'")
        for term in ('À venir', 'Passées', 'Calendrier', 'Nouvel événement'):
            self.assertIn(term, text, term)
        text = self._fr('/my/event/%s' % self.event.id).replace('&#39;', "'")
        for term in ('Ajouter ma feuille de temps', 'Mes feuilles de temps', "Modifier l'événement",
                     'Heures de couverture'):
            self.assertIn(term, text, term)
        text = self._fr('/my/event/create').replace('&#39;', "'")
        for term in ("Début de l'événement", 'Nouveau lieu', 'Nom du lieu', 'À déterminer'):
            self.assertIn(term, text, term)
        text = self._fr('/my/sc/timesheets').replace('&#39;', "'")
        self.assertIn('Appliquer les filtres', text)
        text = self._fr('/my/notepad').replace('&#39;', "'")
        for term in ('Note rapide', 'Lier cette note (facultatif)', 'Ajouter'):
            self.assertIn(term, text, term)

    def test_p3_owl_strings_served_in_french(self):
        resp = self.url_open('/web/webclient/translations?lang=fr_CA&mods=bemade_sports_clinic')
        messages = {
            m['id']: m['string']
            for m in resp.json()['modules']['bemade_sports_clinic']['messages']}
        for source, french in (('Live', 'En direct'), ('Paused', 'En pause'),
                               ('Tap again to remove', 'Touchez de nouveau pour retirer'),
                               ('Resolve', 'Résoudre'), ('Arrived %s', 'Arrivé à %s'),
                               ('The calendar could not be loaded.', "Le calendrier n'a pas pu être chargé."),
                               ('Expected', 'Attendu')):
            self.assertEqual(messages.get(source), french, source)
