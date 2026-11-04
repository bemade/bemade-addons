"""Task 1624 — the dashboard and « Configurer » render in French (fr_CA),
website-aware (fr_CA on every website + the ``frontend_lang`` cookie when
``website`` is installed). Synthetic fixtures only.

Acceptance criteria:

* UC-I1 The dashboard's section titles, empty states, « À faire » lines,
  window labels and « Configurer » link are French.
* UC-I2 The « Configurer » page (switches, ▲ / ▼ labels, « Réglages »,
  « Portée », filters, « + Ajouter une section », « Rétablir par défaut »)
  is French, and so is a refusal (a Python string).
* UC-I3 (review round 1, 2026-10-29) « Joueurs que je suis », « Feuilles de
  temps manquantes » (+ « Ajouter ma feuille de temps », « Jours en
  arrière »), the event « Détails » and the « Suivre » toggle are French;
  a coach reads « Événements à venir ».
* UC-I4 (review round 2, 2026-10-29) the zones of « Configurer » (Gauche,
  Droite, Bas — Python labels), « Déplacer vers » and the drag handle's
  label are French.
"""
from datetime import timedelta

import json

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common


@tagged('post_install', '-at_install')
class TestDashboardI18n1624(Dashboard1624Common):

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
        (cls.tp | cls.coach).write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        # Unescaped (« Aujourd'hui »), plus the OWL props (JSON) decoded.
        tree = lxml_html.fromstring(resp.text)
        props = [json.dumps(json.loads(value), ensure_ascii=False)
                 for value in tree.xpath('//owl-component/@props')]
        return ' '.join(' '.join([tree.text_content()] + props + [resp.text]).split())

    def test_dashboard_in_french(self):
        self.red.sudo().write({'pending_removal': True, 'pending_removal_team_id': self.team_a.id})
        self._login_tp()
        text = self._fr('/my/home')
        for term in ('Tableau de bord', 'Configurer', "Aujourd'hui", 'À faire',
                     'Changements récents', 'Joueurs à surveiller', 'Annonces', 'Indicateurs',
                     'Couvertures à venir', 'Toutes mes équipes', 'Demandes de retrait',
                     "Cliniques aujourd'hui", 'Aucun changement récent',
                     'Calendrier', "Jusqu'au", '(14 prochains jours)'):
            self.assertIn(term, text, term)
        for term in ('>Today<', 'Upcoming coverage', 'All my teams', 'Removal requests'):
            self.assertNotIn(term, text, term)

    def test_configure_in_french(self):
        self._login_tp()
        text = self._fr('/my/app/dashboard/configure')
        for term in ('Configurer le tableau de bord', 'Réglages', 'Portée', 'Titre',
                     'Monter', 'Descendre', 'Ajouter une section', 'Rétablir par défaut',
                     'Retour au tableau de bord', 'Rouge et jaune', 'Par défaut (14 jours)',
                     'Blessures à vérifier', 'Équipes', 'Équipes de ces organisations'):
            self.assertIn(term, text, term)
        for term in ('Move up', 'Restore the default', 'Add a section', '>Settings<'):
            self.assertNotIn(term, text, term)
        resp = self.url_open('/my/app/dashboard/configure/remove', data={
            'csrf_token': self._csrf(), 'instance_id': 'watch'},
            headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('désactivée', json.loads(resp.text)['error'])

    def test_round1_in_french(self):
        start = fields.Datetime.now() - timedelta(days=2)
        self.env['sports.event'].create({
            'name': 'DB Missing FR', 'event_type': 'game',
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'team_ids': [Command.set(self.team_a.ids)],
            'assigned_staff_ids': [Command.set(self.tp.ids)], 'state': 'confirmed'})
        self._login_tp()
        text = self._fr('/my/home')
        for term in ('Joueurs que je suis', 'Feuilles de temps manquantes',
                     'Ajouter ma feuille de temps', '(30 derniers jours)', 'Détails',
                     'Personnel assigné', "Ouvrir l'événement", 'Vous ne suivez encore aucun joueur'):
            self.assertIn(term, text, term)
        for term in ('Players I follow', 'Missing timesheets', 'Add My Timesheet', 'Open the event'):
            self.assertNotIn(term, text, term)
        text = self._fr('/my/player/%s/row-detail' % self.red.id)
        self.assertIn('Suivre', text)
        self.assertNotIn('>Follow<', text)
        text = self._fr('/my/app/dashboard/configure')
        self.assertIn('Jours en arrière', text)
        self._login_coach()
        text = self._fr('/my/home')
        self.assertIn('Événements à venir', text)
        self.assertNotIn('Couvertures à venir', text)

    def test_zones_in_french(self):
        self._login_tp()
        text = self._fr('/my/app/dashboard/configure')
        for term in ('Gauche', 'Droite', 'Bas', 'Déplacer vers', 'Glisser pour déplacer'):
            self.assertIn(term, text, term)
        for term in ('>Left<', '>Right<', '>Bottom<', 'Move to', 'Drag to move'):
            self.assertNotIn(term, text, term)
