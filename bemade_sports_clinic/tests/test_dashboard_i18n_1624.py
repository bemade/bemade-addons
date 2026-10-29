"""Task 1624 — the dashboard and « Configurer » render in French (fr_CA),
website-aware (fr_CA on every website + the ``frontend_lang`` cookie when
``website`` is installed). Synthetic fixtures only.

Acceptance criteria:

* UC-I1 The dashboard's section titles, empty states, « À faire » lines,
  window labels and « Configurer » link are French.
* UC-I2 The « Configurer » page (switches, ▲ / ▼ labels, « Réglages »,
  « Portée », filters, « + Ajouter une section », « Rétablir par défaut »)
  is French, and so is a refusal (a Python string).
"""
import json

from lxml import html as lxml_html

from odoo import Command
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
