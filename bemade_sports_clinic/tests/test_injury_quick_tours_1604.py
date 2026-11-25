"""Task 1604 — quick « Vérifier » / « Résoudre » in a browser (phone 390 px
and laptop 1366 px). Synthetic fixtures only.

Acceptance criteria (static/tests/tours/sc_injury_quick_1604_tours.js):

* AC-T1 A therapist taps « Verify » on an unverified injury's COLLAPSED
  row: the card does not open, the row turns into « Resolve » in place (no
  reload); the injury is active and its verification To-Do closed.
* AC-T2 « Resolve » on an active injury's collapsed row opens the sheet
  (date = today, editable; the card stays closed); the confirm resolves it
  on the chosen date and — the player's last active injury — opens the
  #1603 « last_resolved » proposal with that date; the row loses its
  button in place (no reload).
* AC-T3 « Verify » on an OPEN card's row (task 1616: the former injury
  page): the row then offers « Resolve », the card stays open (no reload).
"""
from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient_injury import VERIFY_INJURY_SUMMARY
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

D = fields.Date.to_date


class QuickToursCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.injury.write({'diagnosis': 'Synthetic ankle'})
        cls.strain = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic strain'})
        cls.strain.with_context(mail_notrack=True).write({'stage': 'unverified'})
        cls.todo = env['mail.activity'].create({
            'res_model_id': env['ir.model']._get('sports.patient').id,
            'res_id': cls.player.id,
            'injury_id': cls.strain.id,
            'activity_type_id': env.ref('mail.mail_activity_data_todo').id,
            'summary': '[Injury: Synthetic strain] ' + VERIFY_INJURY_SUMMARY,
            'user_id': cls.tp.id,
            'date_deadline': fields.Date.today(),
        })
        cls.tp.write({'tz': 'UTC'})

    def setUp(self):
        super().setUp()
        self._switch(True)


class QuickTours:

    def _player_url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id

    def test_verify_row(self):
        self.start_tour(self._player_url(), 'sc_1604_verify_row', login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.strain.stage, 'active')
        self.assertFalse(self.todo.active)

    def test_resolve_row(self):
        self.player.write({'predicted_return_date': '2030-03-01'})
        self.start_tour(self._player_url(), 'sc_1604_resolve_row', login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.injury.stage, 'resolved')
        self.assertEqual(self.injury.resolution_date, D('2025-01-15'))
        # Dismissed: the proposal wrote nothing.
        self.assertEqual(self.player.predicted_return_date, D('2030-03-01'))

    def test_page_verify(self):
        # Task 1616: the injury page is the open card now.
        self.start_tour('%s&injury=%s' % (self._player_url(), self.strain.id), 'sc_1604_page_verify',
                        login='pc.tp@example.com')
        self.env.invalidate_all()
        self.assertEqual(self.strain.stage, 'active')


@tagged('post_install', '-at_install')
class TestInjuryQuickToursPhone1604(QuickTours, QuickToursCommon):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestInjuryQuickToursLaptop1604(QuickTours, QuickToursCommon):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
