"""Task 1630 — the allergies / medical-alert strings in French (fr_CA),
checked by RENDER, website-aware (fr_CA on every website + the
``frontend_lang`` cookie). Synthetic fixtures only.

* FR-1 Player header + popups: « Allergies », « Alerte médicale », the
  levels « Aucune » / « Non urgente » / « Urgente – risque vital » / « Non
  renseigné », EpiPen « Oui » / « Non » (task 1677: no level editor).
* FR-2 Infos tab: « Autres antécédents médicaux ».
* FR-3 Task 1677: the popups' lists — « Ajouter une allergie / une
  condition », « Risque vital », « Premiers soins », « Emplacement /
  instructions », « Aucune allergie / condition connue », « Ancien texte (à
  valider) », and a route refusal in French.
* FR-4 Legacy compact lines and the backend: « Allergies (urgente – risque
  vital, EpiPen) : … »; the review action / menu « Alertes médicales à
  valider », the filter « Alertes à valider », the group « Santé », the
  field labels (``arch_db`` / field translations).
"""
import re

from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestMedicalAlertsI18n1630(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_medical(cls.player, allergies=[('Synthetic kiwi', True)], conditions=[], epipen=True,
                    none_allergy=False, none_condition=False)
        cls.player.sudo().write({'medical_history_other': 'Synthetic fracture'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _url(self, tab='injuries'):
        return '/my/player?player_id=%s&tab=%s' % (self.player.id, tab)

    @staticmethod
    def _squash(text):
        return re.sub(r'\s+', ' ', text)

    def test_header_and_popups_in_french(self):
        self._login_tp()
        text = self._fr(self._url()).replace('&#39;', "'")
        tree = lxml_html.fromstring(text)
        pills = tree.xpath('//*[@data-sc-section="player.medical"]//button[@data-sc-med-pill]')
        self.assertEqual([' '.join(p.text_content().split()) for p in pills], ['Synthetic kiwi', 'Alerte médicale'])
        self.assertEqual(pills[0].get('title'), 'Allergies : Urgente – risque vital')
        self.assertEqual(pills[1].get('title'), 'Alerte médicale : Non renseigné')
        allergy = self._squash(tree.xpath('//dialog[@id="sc_med_player_allergy_%s"]' % self.player.id)[0].text_content())
        alert = self._squash(tree.xpath('//dialog[@id="sc_med_player_medical_alert_%s"]' % self.player.id)[0].text_content())
        for term in ('Urgente – risque vital', 'Risque vital', 'Ajouter une allergie', 'Emplacement / instructions',
                     'EpiPen Oui', 'Nom'):
            self.assertIn(term, allergy, term)
        for term in ('Non renseigné', 'Ajouter une condition', 'Premiers soins', 'Aucune condition connue'):
            self.assertIn(term, alert, term)
        # The old text, while to validate.
        self.player.sudo().write({'medical_alert_review': True, 'allergy_details': 'Synthetic old'})
        text = self._fr(self._url())
        self.assertIn('Ancien texte (à valider)', text)
        # A coach: the red pill and its popup, in French.
        self._login_coach()
        text = self._fr(self._url())
        self.assertIn('Urgente – risque vital', text)
        self.assertNotIn('Non renseigné', text)

    def test_infos_card_in_french(self):
        self._login_tp()
        text = self._fr(self._url('info'))
        self.assertIn('Autres antécédents médicaux', text)

    def test_route_refusal_in_french(self):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        self.tp.sudo().lang = 'fr_CA'
        resp = self.url_open('/my/app/medical/%s/set' % self.player.id, data={
            'field': 'allergy_none_confirmed', 'value': '1', 'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(resp.json()['message'],
                         "Retirez d'abord les éléments de la liste : « aucune connue » vaut pour une liste vide.")

    def test_legacy_lines_and_backend_in_french(self):
        fr = self.env(context={'lang': 'fr_CA'})
        player = self.player.with_env(fr)
        lines = [line['text'] for line in player._sc_medical_summary_lines(tp=True)]
        self.assertEqual(lines, ['Allergies (urgente – risque vital, EpiPen) : Synthetic kiwi (risque vital)'])
        self.assertEqual(fr.ref('bemade_sports_clinic.action_patient_medical_review').name,
                         'Alertes médicales à valider')
        self.assertEqual(fr.ref('bemade_sports_clinic.sports_clinic_medical_review_menu').name,
                         'Alertes médicales à valider')
        search = fr.ref('bemade_sports_clinic.sports_patient_view_search').with_env(fr).arch_db
        self.assertIn('Alertes à valider', search)
        form = fr.ref('bemade_sports_clinic.sports_patient_view_form').with_env(fr).arch_db
        self.assertIn('Santé', form)
        self.assertIn('Allergies et conditions', form)
        labels = fr['sports.patient'].fields_get(
            ['allergy_level', 'allergy_details', 'allergy_epipen', 'medical_alert_level',
             'medical_alert_details', 'medical_history_other', 'medical_alert_review',
             'allergy_epipen_note', 'allergy_none_confirmed', 'medical_none_confirmed',
             'medical_alert_critical_ids'],
            ['string', 'selection'])
        self.assertEqual(labels['allergy_level']['string'], "Niveau d'allergies")
        self.assertEqual(labels['allergy_details']['string'], 'Détails des allergies')
        self.assertEqual(labels['medical_alert_level']['string'], "Niveau d'alerte médicale")
        self.assertEqual(labels['medical_alert_details']['string'], "Détails de l'alerte médicale")
        self.assertEqual(labels['medical_history_other']['string'], 'Autres antécédents médicaux')
        self.assertEqual(labels['medical_alert_review']['string'], 'À valider')
        self.assertEqual(labels['allergy_epipen_note']['string'], 'Note EpiPen')
        self.assertEqual(labels['allergy_none_confirmed']['string'], 'Aucune allergie connue')
        self.assertEqual(labels['medical_none_confirmed']['string'], 'Aucune condition connue')
        self.assertEqual(labels['medical_alert_critical_ids']['string'], 'Conditions médicales')
        self.assertEqual(dict(labels['allergy_level']['selection']),
                         {'none': 'Aucune', 'minor': 'Non urgente', 'urgent': 'Urgente – risque vital'})
        items = fr['sports.patient.critical.item'].fields_get(['life_threatening', 'first_aid_note'], ['string'])
        self.assertEqual((items['life_threatening']['string'], items['first_aid_note']['string']),
                         ('Risque vital', 'Premiers soins'))
        review = fr.ref('bemade_sports_clinic.sports_patient_view_list_medical_review').with_env(fr).arch_db
        self.assertIn('Alertes médicales à valider', review)
        # #1628 items.
        todo = player._sc_incomplete_labels()
        self.assertEqual((todo['allergy_level'], todo['medical_alert_level']), ('Allergies', 'Alerte médicale'))

    def test_legacy_form_in_french(self):
        self._switch(False)
        self._login_tp()
        text = self._fr('/my/player/edit?patient_id=%s' % self.player.id).replace('&#39;', "'")
        self.assertIn('Autres antécédents médicaux', text)
        self.assertNotIn("Niveau d'allergies", text)
