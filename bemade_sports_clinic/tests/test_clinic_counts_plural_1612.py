"""Task 1612 — the clinic worklist counts line agrees in number.
Synthetic fixtures only.

Use case: the clinic page's « Présences : … » line read « 1 arrivés ».

Acceptance criteria:

* AC1 Each count takes its singular with 1 and its plural with 2+
  (English: « 1 no-show » / « 2 no-shows »).
* AC2 fr_CA: « 1 arrivé » / « 2 arrivés », same for attendu(s), vu(s),
  absent(s), non inscrit(s); zero takes the singular (« 0 vu »).
* AC3 The « unregistered » count is still appended only when non-zero.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.controllers.clinic_portal import ClinicPortal
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


def _counts(expected=0, arrived=0, seen=0, no_show=0, unregistered=0):
    return {'expected': expected, 'arrived': arrived, 'seen': seen,
            'no_show': no_show, 'unregistered': unregistered}


@tagged('post_install', '-at_install')
class TestClinicCountsPlural1612(TransactionCase):

    # -- AC1 / AC3 -------------------------------------------------------
    def test_english_singular_and_plural(self):
        line = ClinicPortal._attendance_counts_line(_counts(1, 1, 1, 1, 1))
        self.assertEqual(
            line, '1 expected · 1 arrived · 1 seen · 1 no-show · 1 unregistered')
        line = ClinicPortal._attendance_counts_line(_counts(2, 3, 4, 5, 6))
        self.assertEqual(
            line, '2 expected · 3 arrived · 4 seen · 5 no-shows · 6 unregistered')
        line = ClinicPortal._attendance_counts_line(_counts())
        self.assertEqual(line, '0 expected · 0 arrived · 0 seen · 0 no-shows')


@tagged('post_install', '-at_install')
class TestClinicCountsPluralFr1612(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        cls.clinic = cls.env['sports.event'].create({
            'name': 'FR 1612 Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': now, 'date_end': now + timedelta(hours=2), 'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        cls.mate = cls.env['sports.patient'].create({
            'first_name': 'Mate', 'last_name': 'Synthetic',
            'team_ids': [Command.set([cls.team_a.id])],
        })
        Attendance = cls.env['sports.clinic.attendance']
        Attendance.create({'event_id': cls.clinic.id, 'patient_id': cls.player.id,
                           'state': 'arrived'})
        Attendance.create({'event_id': cls.clinic.id, 'patient_id': cls.mate.id})
        Attendance.create({'event_id': cls.clinic.id, 'patient_id': cls.player_b.id})

    # -- AC2 -------------------------------------------------------------
    def test_french_singular_and_plural(self):
        self._switch(True)
        self._login_tp()
        self._fr('/my/clinics')
        data = self.url_open('/my/clinic/%s/worklist/data' % self.clinic.id).json()
        line = data['countsLine']
        self.assertEqual(line, 'Présences : 2 attendus · 1 arrivé · 0 vu · 0 absent', line)
