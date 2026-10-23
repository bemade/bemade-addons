"""Task 1630 — the allergies / medical-alert strings in French (fr_CA),
checked by RENDER, website-aware (fr_CA on every website + the
``frontend_lang`` cookie). Synthetic fixtures only.

* FR-1 Player header + popups: « Allergies », « Alerte médicale », the
  levels « Aucune » / « Non urgente » / « Urgente – risque vital » / « Non
  renseigné », « Aucun détail. », the edit labels « Niveau d'allergies »,
  « Détails des allergies », « Niveau d'alerte médicale », « Détails de
  l'alerte médicale », EpiPen « Oui » / « Non ».
* FR-2 Infos tab: « Autres antécédents médicaux ».
* FR-3 Save answers: the level display « Non urgente » / « Non renseigné ».
* FR-4 Legacy compact lines and the backend: « Allergies (urgente – risque
  vital, EpiPen) : … »; the review action / menu « Alertes médicales à
  valider », the filter « Alertes à valider », the group « Santé », the
  field labels (``arch_db`` / field translations).
"""
import json

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestMedicalAlertsI18n1630(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.sudo().write({
            'allergy_level': 'urgent', 'allergy_epipen': True, 'allergy_details': 'Synthetic kiwi',
            'medical_alert_level': False, 'medical_history_other': 'Synthetic fracture',
        })

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _url(self, tab='injuries'):
        return '/my/player?player_id=%s&tab=%s' % (self.player.id, tab)

    def test_header_and_popups_in_french(self):
        self._login_tp()
        text = self._fr(self._url()).replace('&#39;', "'")
        tree = lxml_html.fromstring(text)
        pills = tree.xpath('//*[@data-sc-section="player.medical"]//button[@data-sc-med-pill]')
        self.assertEqual([' '.join(p.text_content().split()) for p in pills], ['Allergies', 'Alerte médicale'])
        self.assertEqual(pills[0].get('title'), 'Allergies : Urgente – risque vital')
        self.assertEqual(pills[1].get('title'), 'Alerte médicale : Non renseigné')
        for term in ('Urgente – risque vital', 'Non renseigné', 'Aucun détail.'):
            self.assertIn(term, text, term)
        labels = {json.loads(p)['field']: json.loads(p) for p in tree.xpath(
            '//dialog[starts-with(@id, "sc_med_player_")]//owl-component/@props')}
        self.assertEqual(labels['allergy_level']['label'], "Niveau d'allergies")
        self.assertEqual(labels['allergy_details']['label'], 'Détails des allergies')
        self.assertEqual(labels['medical_alert_level']['label'], "Niveau d'alerte médicale")
        self.assertEqual(labels['medical_alert_details']['label'], "Détails de l'alerte médicale")
        # Task 1653: a set level offers the three levels only.
        self.assertEqual([o[1] for o in labels['allergy_level']['options']],
                         ['Aucune', 'Non urgente', 'Urgente – risque vital'])
        self.assertEqual([o[1] for o in labels['allergy_epipen']['options']], ['Oui', 'Non'])
        self.assertEqual(labels['allergy_epipen']['label'], 'EpiPen')
        # A coach: the red pill and its popup, in French.
        self._login_coach()
        text = self._fr(self._url())
        self.assertIn('Urgente – risque vital', text)
        self.assertNotIn('Non renseigné', text)

    def test_infos_card_in_french(self):
        self._login_tp()
        text = self._fr(self._url('info'))
        self.assertIn('Autres antécédents médicaux', text)

    def test_save_display_in_french(self):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        # Task 1653: once set, a level can't go back to « Non renseigné ».
        for value, display in (('minor', 'Non urgente'), ('none', 'Aucune')):
            self.player.invalidate_recordset()
            resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
                'field': 'medical_alert_level', 'value': value, 'csrf_token': self._csrf(),
                'write_date': fields.Datetime.to_string(self.player.sudo().write_date)}, allow_redirects=False)
            self.assertEqual(resp.status_code, 200, resp.text)
            self.assertEqual(resp.json()['display'], display)

    def test_legacy_lines_and_backend_in_french(self):
        fr = self.env(context={'lang': 'fr_CA'})
        player = self.player.with_env(fr)
        lines = [line['text'] for line in player._sc_medical_summary_lines(tp=True)]
        self.assertEqual(lines, ['Allergies (urgente – risque vital, EpiPen) : Synthetic kiwi'])
        self.assertEqual(fr.ref('bemade_sports_clinic.action_patient_medical_review').name,
                         'Alertes médicales à valider')
        self.assertEqual(fr.ref('bemade_sports_clinic.sports_clinic_medical_review_menu').name,
                         'Alertes médicales à valider')
        search = fr.ref('bemade_sports_clinic.sports_patient_view_search').with_env(fr).arch_db
        self.assertIn('Alertes à valider', search)
        form = fr.ref('bemade_sports_clinic.sports_patient_view_form').with_env(fr).arch_db
        self.assertIn('Santé', form)
        labels = fr['sports.patient'].fields_get(
            ['allergy_level', 'allergy_details', 'allergy_epipen', 'medical_alert_level',
             'medical_alert_details', 'medical_history_other', 'medical_alert_review'],
            ['string', 'selection'])
        self.assertEqual(labels['allergy_level']['string'], "Niveau d'allergies")
        self.assertEqual(labels['allergy_details']['string'], 'Détails des allergies')
        self.assertEqual(labels['medical_alert_level']['string'], "Niveau d'alerte médicale")
        self.assertEqual(labels['medical_alert_details']['string'], "Détails de l'alerte médicale")
        self.assertEqual(labels['medical_history_other']['string'], 'Autres antécédents médicaux')
        self.assertEqual(labels['medical_alert_review']['string'], 'À valider')
        self.assertEqual(dict(labels['allergy_level']['selection']),
                         {'none': 'Aucune', 'minor': 'Non urgente', 'urgent': 'Urgente – risque vital'})
        review = fr.ref('bemade_sports_clinic.sports_patient_view_list_medical_review').with_env(fr).arch_db
        self.assertIn('Alertes médicales à valider', review)
        # #1628 items.
        items = player._sc_incomplete_labels()
        self.assertEqual((items['allergy_level'], items['medical_alert_level']),
                         ("Niveau d'allergies", 'Alerte médicale'))

    def test_legacy_form_in_french(self):
        self._switch(False)
        self._login_tp()
        text = self._fr('/my/player/edit?patient_id=%s' % self.player.id).replace('&#39;', "'")
        for term in ("Niveau d'allergies", 'Détails des allergies', "Niveau d'alerte médicale",
                     'Autres antécédents médicaux', '— Choisir —', 'Urgente – risque vital'):
            self.assertIn(term, text, term)
