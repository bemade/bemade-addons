"""Task 1603 — « Retour prévu » and the follow-up proposals in a browser
(phone 390 px and laptop 1366 px). Synthetic fixtures only.

Acceptance criteria (static/tests/tours/sc_retour_prevu_1603_tours.js):

* AC-T1 Injury -> player: a therapist changes an active injury's predicted
  resolution date; the sheet proposes Retour prévu = the latest active date
  (editable); the edited date is applied; the header field shows it without
  a reload, and the team roster row shows the new Retour prévu.
* AC-T2 Player -> injuries: a therapist changes Retour prévu in the header;
  the sheet lists both active injuries, ticked; unticking one and applying
  writes only the other; its card's read view follows in place.
* AC-T3 Resolve the last active injury: the sheet proposes clearing Retour
  prévu and the actual return date (edited); applied, the header shows
  Retour prévu cleared and the « Actual return » chip.
* AC-T4 Dismiss: the sheet closes; only the triggering field was saved.
"""
from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

D = fields.Date.to_date


class RetourPrevuTourCommon(AppShellCommon):
    """Fixtures only (the tagged subclasses inherit the tours below)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.injury.write({'diagnosis': 'Synthetic ankle', 'predicted_resolution_date': '2030-03-01'})
        cls.injury_b = cls.env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic knee',
            'predicted_resolution_date': '2030-02-01'})
        cls.injury_b.with_context(mail_notrack=True).write({'stage': 'active'})
        cls.tp.write({'tz': 'UTC'})

    def setUp(self):
        super().setUp()
        self._switch(True)


class RetourPrevuTours:

    def _player_url(self, **extra):
        url = '/my/player?player_id=%s&tab=injuries' % self.player.id
        return url + ''.join('&%s=%s' % kv for kv in extra.items())

    def test_injury_to_player(self):
        # Injured (the roster row shows « Retour prévu » for injured players).
        self.player.write({'match_status': 'no', 'practice_status': 'no'})
        self.start_tour(self._player_url(injury=self.injury.id, team_id=self.team_a.id),
                        'sc_1603_injury_to_player', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.predicted_resolution_date, D('2030-05-01'))
        self.assertEqual(self.player.predicted_return_date, D('2030-05-03'))

    def test_player_to_injuries(self):
        self.start_tour(self._player_url(), 'sc_1603_player_to_injuries', login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.player.predicted_return_date, D('2030-06-01'))
        self.assertEqual(self.injury_b.predicted_resolution_date, D('2030-06-01'))
        self.assertEqual(self.injury.predicted_resolution_date, D('2030-03-01'))

    def test_last_resolved(self):
        self.injury_b.with_context(mail_notrack=True).write({'stage': 'resolved'})
        self.player.write({'predicted_return_date': '2030-03-01'})
        self.start_tour(self._player_url(injury=self.injury.id), 'sc_1603_last_resolved',
                        login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.injury.stage, 'resolved')
        self.assertFalse(self.player.predicted_return_date)
        self.assertEqual(self.player.return_date, D('2030-01-31'))

    def test_dismiss(self):
        self.start_tour(self._player_url(), 'sc_1603_dismiss', login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.player.predicted_return_date, D('2030-06-01'))
        self.assertEqual(self.injury.predicted_resolution_date, D('2030-03-01'))
        self.assertEqual(self.injury_b.predicted_resolution_date, D('2030-02-01'))


@tagged('post_install', '-at_install')
class TestRetourPrevuToursPhone1603(RetourPrevuTours, RetourPrevuTourCommon):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestRetourPrevuToursLaptop1603(RetourPrevuTours, RetourPrevuTourCommon):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
