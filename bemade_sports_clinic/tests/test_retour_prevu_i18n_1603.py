"""Task 1603 — every new string renders in French (fr_CA). Checked by
RENDER, website-aware (fr_CA on every website + the ``frontend_lang``
cookie). Synthetic fixtures only.

* UC-F1 The player header: « Retour prévu » (therapist field and coach read
  view); the proposal sheet's « Appliquer », « Ignorer », « Les
  modifications n'ont pas pu être appliquées. ».
* UC-F2 The three proposals (save answers, the user's language): titles,
  messages, row labels, « Aucune date »; the apply answer « Modifications
  appliquées. ».
"""
import json

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestRetourPrevuI18n1603(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury.write({'diagnosis': 'Synthetic ankle', 'predicted_resolution_date': '2030-03-01'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id

    def _post(self, record, field, value):
        record.invalidate_recordset()
        resp = self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value, 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(record.sudo().write_date)}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()['propose']

    def test_header_and_sheet_in_french(self):
        self._login_tp()
        text = self._fr(self._url()).replace('&#39;', "'")
        for term in ('Appliquer', 'Ignorer', "Les modifications n'ont pas pu être appliquées."):
            self.assertIn(term, text, term)
        # The therapist's field: the label travels in the island's props.
        field = lxml_html.fromstring(text).xpath(
            '//*[@data-sc-section="player.predicted_return"]//owl-component')[0]
        self.assertEqual(json.loads(field.get('props'))['label'], 'Retour prévu')
        # Review fixes 2026-10-18: the read view shows « Retour prévu » while
        # the player is not Play OK and the date is set.
        self.player.sudo().write({'predicted_return_date': '2030-03-01', 'match_status': 'no',
                                  'practice_status': 'no'})
        self._login_coach()
        self.assertIn('Retour prévu', self._fr(self._url()))

    def test_proposals_in_french(self):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        proposal = self._post(self.injury, 'predicted_resolution_date', '2030-04-01')
        self.assertEqual(proposal['title'], 'Mettre à jour le retour prévu du joueur ?')
        self.assertIn('La date prévue de résolution la plus tardive', proposal['message'])
        self.assertEqual(proposal['items'][0]['label'], 'Retour prévu')
        proposal = self._post(self.player, 'predicted_return_date', '2030-05-01')
        self.assertEqual(proposal['title'], 'Aligner les dates prévues de résolution des blessures ?')
        self.assertIn('Décochez les blessures', proposal['message'])
        self.player.write({'predicted_return_date': '2030-05-01'})
        proposal = self._post(self.injury, 'stage', 'resolved')
        self.assertEqual(proposal['title'], 'Plus aucune blessure active')
        self.assertIn("C'était la dernière blessure active du joueur.", proposal['message'])
        labels = {item['field']: item for item in proposal['items']}
        self.assertEqual(labels['return_date']['label'], 'Date de retour réelle')
        self.assertEqual(labels['predicted_return_date']['proposed_display'], 'Aucune date')
        resp = self.url_open('/my/app/apply-proposal', data={
            'patient_id': self.player.id, 'csrf_token': self._csrf(),
            'changes': json.dumps([{'model': 'sports.patient', 'id': self.player.id,
                                    'field': 'predicted_return_date', 'value': ''}])})
        self.assertEqual(resp.json()['message'], 'Modifications appliquées.')
